"""transform.py — Calculer l'étoile olap à partir des lignes de l'OLTP, sans base.

Chantier FLX, fiche FLX6. Entrée : le dictionnaire rendu par extract.py.
Sortie : les dimensions et les faits, prêts à charger, et un rapport qualité.
Tout se teste sans base (airflow/tests/test_olap_transform.py).

Les mesures suivent l'en-tête de docker/init-v3/08_olap.sql :
  - delai_semaines : (jour de l'acte - signature du mandat RACINE de la
    chaîne) // 7, comme payment_calculation_service.py (ADR-050) ; vide si
    cette signature manque ;
  - nb_visites_avant_achat : visites 'client' de tous les mandats de la
    chaîne, datées au plus tard le jour de l'acte (ADR-048 point 4, ADR-053) ;
  - commission_chasseur : payment.amount ; vide tant que la vente n'a pas de
    paiement — la vente est gardée, pas rejetée (fiche FLX6).

Une vente est rejetée seulement si elle ne peut pas entrer dans l'étoile
sans mentir : référence introuvable, ou délai négatif (acte avant la
signature du mandat) que le CHECK de fait_ventes refuserait.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

Row = dict[str, object]
SectorKey = tuple[object, object, object]  # (pays, code_postal, ville)


@dataclass
class Star:
    """Ce que load.py écrit, et le rapport du passage."""

    dim_temps: list[Row] = field(default_factory=list)
    dim_chasseur: list[Row] = field(default_factory=list)
    dim_client: list[Row] = field(default_factory=list)
    dim_bien: list[Row] = field(default_factory=list)
    dim_secteur: list[Row] = field(default_factory=list)
    facts: list[Row] = field(default_factory=list)
    rejects: list[Row] = field(default_factory=list)

    def report(self) -> dict[str, object]:
        """Rapport qualité (cours CRS06) : lues, chargées, rejetées par raison."""
        read = len(self.facts) + len(self.rejects)
        by_reason: dict[str, int] = {}
        for r in self.rejects:
            reason = str(r["reason"])
            by_reason[reason] = by_reason.get(reason, 0) + 1
        return {
            "read": read,
            "loaded": len(self.facts),
            "invalid_count": len(self.rejects),
            "pass_rate": round(len(self.facts) / read, 4) if read else 1.0,
            "rejected_by_reason": by_reason,
        }


def day_row(day: date) -> Row:
    """Une ligne de dim_temps."""
    iso = day.isocalendar()
    return {
        "jour": day,
        "annee": day.year,
        "trimestre": (day.month - 1) // 3 + 1,
        "mois": day.month,
        "semaine_iso": iso[1],
        "jour_semaine_iso": iso[2],
    }


def delay_weeks(signed: date | None, sale_day: date) -> int | None:
    """Semaines pleines entre la signature du mandat racine et l'acte ; vide sans signature."""
    if signed is None:
        return None
    return (sale_day - signed).days // 7


def chain_roots(mandates: dict[int, Row]) -> dict[int, int]:
    """Le mandat racine de chaque mandat (en remontant id_mandate_parent)."""
    roots: dict[int, int] = {}
    for start in mandates:
        current, seen = start, set()
        while True:
            parent = mandates[current].get("id_mandate_parent")
            if parent is None or parent not in mandates or parent in seen:
                break
            seen.add(current)
            current = int(parent)  # pyright: ignore[reportArgumentType] -- un id de mandat est un entier
        roots[start] = current
    return roots


def _year(value: object) -> int | None:
    if isinstance(value, (date, datetime)):
        return value.year
    return None


def _index(rows: list[Row]) -> dict[int, Row]:
    return {int(r["id"]): r for r in rows}  # pyright: ignore[reportArgumentType] -- id entier


def build_star(data: dict[str, list[Row]]) -> Star:
    """Dimensions et faits, à partir des lignes de extract.py."""
    mandates, hunters = _index(data["mandates"]), _index(data["hunters"])
    clients, estates = _index(data["clients"]), _index(data["estates"])
    roots = chain_roots(mandates)
    visits_by_root: dict[int, list[date]] = {}
    for v in data["visits"]:
        root = roots.get(int(v["id_mandate"]))  # pyright: ignore[reportArgumentType] -- id entier
        if root is not None:
            visits_by_root.setdefault(root, []).append(v["visit_date"])  # pyright: ignore[reportArgumentType] -- DATE

    star = Star()
    days: dict[date, Row] = {}
    hunter_rows: dict[int, Row] = {}
    client_rows: dict[int, Row] = {}
    estate_rows: dict[int, Row] = {}
    sectors: dict[SectorKey, Row] = {}

    for s in data["sales"]:
        sale_day: date = s["signature_date"]  # pyright: ignore[reportAssignmentType] -- DATE
        mandate = mandates.get(int(s["id_mandate"]))  # pyright: ignore[reportArgumentType] -- id entier
        estate = estates.get(int(s["id_estate"]))  # pyright: ignore[reportArgumentType] -- id entier
        reason = None
        if mandate is None:
            reason = "unknown_mandate"
        elif estate is None:
            reason = "unknown_estate"
        elif int(mandate["id_hunter"]) not in hunters:  # pyright: ignore[reportArgumentType] -- id entier
            reason = "unknown_hunter"
        elif int(mandate["id_client"]) not in clients:  # pyright: ignore[reportArgumentType] -- id entier
            reason = "unknown_client"
        if reason is not None or mandate is None or estate is None:
            star.rejects.append({"id_sale": s["id"], "reason": reason})
            continue

        root_id = roots[int(mandate["id"])]  # pyright: ignore[reportArgumentType] -- id entier
        delay = delay_weeks(mandates[root_id]["signature_date"], sale_day)  # pyright: ignore[reportArgumentType] -- DATE ou vide
        if delay is not None and delay < 0:
            star.rejects.append({"id_sale": s["id"], "reason": "sale_before_mandate_signature"})
            continue

        id_hunter, id_client = int(mandate["id_hunter"]), int(mandate["id_client"])  # pyright: ignore[reportArgumentType] -- ids entiers
        hunter, client = hunters[id_hunter], clients[id_client]
        days.setdefault(sale_day, day_row(sale_day))
        hunter_rows.setdefault(id_hunter, {
            "id_hunter": id_hunter,
            "annee_embauche": _year(hunter["hire_date"]),
            "est_ia": hunter["is_hunter_ai"],
            "a_carte_t": hunter["is_carte_t"],
            "pays": hunter["country_iso"],
        })
        client_rows.setdefault(id_client, {
            "id_client": id_client,
            "annee_inscription": _year(client["created_at"]),
            "ville": client["town"],
            "pays": client["country_iso"],
        })
        id_estate = int(estate["id"])  # pyright: ignore[reportArgumentType] -- id entier
        estate_rows.setdefault(id_estate, {
            "id_estate": id_estate,
            "type_bien": estate["estate_type"],
            "typologie": estate["typology"],
            "surface": estate["surface"],
            "nb_pieces": estate["nb_rooms"],
            "classe_energie": estate["energy_class"],
            "annee_construction": _year(estate["construction_date"]),
            "est_importe": bool(estate["is_imported"]),
        })
        sector: SectorKey = (estate["country_iso"], estate["postal_code"], estate["town"])
        sectors.setdefault(sector, {"pays": sector[0], "code_postal": sector[1], "ville": sector[2]})

        star.facts.append({
            "id_sale": s["id"],
            "jour": sale_day,
            "id_hunter": id_hunter,
            "id_client": id_client,
            "id_estate": id_estate,
            "pays": sector[0],
            "code_postal": sector[1],
            "ville": sector[2],
            "montant_bien": s["purchase_amount"],
            "honoraires": s["fees_amount"],
            "commission_chasseur": s["payment_amount"],
            "nb_visites_avant_achat": sum(1 for d in visits_by_root.get(root_id, []) if d <= sale_day),
            "delai_semaines": delay,
            "mandat_exclusif": bool(mandate["is_exclusive"]),
        })

    star.dim_temps = sorted(days.values(), key=lambda r: r["jour"])  # pyright: ignore[reportArgumentType, reportCallIssue] -- dates comparables
    star.dim_chasseur = list(hunter_rows.values())
    star.dim_client = list(client_rows.values())
    star.dim_bien = list(estate_rows.values())
    star.dim_secteur = list(sectors.values())
    return star
