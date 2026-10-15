# COPIE À L'IDENTIQUE (chantier FLX, fiche FLX4, 2026-10-15) — ne pas modifier.
# Source : StarterPack - BASE, outils/generer_annonces.py, commit 1ebca04 du
# 2026-08-19 (sha256 ec23e6229e3bb13f…). Le StarterPack est en lecture seule :
# le DAG annonces_import recopie ce fichier dans <tmp>/outils/ et le lance là,
# il écrit donc dans <tmp>/fixtures/annonces/.
#
"""
Générateur de critères de recherche + annonces immobilières factices.

Simule deux jeux de données liés :
- des critères de recherche (le futur modèle "demandes" structuré évoqué
  au Readme, à opposer au champ texte libre `mandats.description_recherche`
  de l'existant) ;
- des annonces correspondant à ces critères, avec un flux "sale" et
  hétérogène tel qu'on pourrait le recevoir de plusieurs sources différentes
  (agences, particuliers, plateformes) : champs absents ou renommés, dates
  dans des formats variés, géolocalisation pas toujours renseignée, etc.
  Seuls les champs qui définissent la correspondance avec la recherche
  (ville, type de bien, prix, surface) sont garantis présents et cohérents
  avec le budget/la surface minimale demandés ; le reste reste aléatoire.

Le script est cumulatif : chaque exécution AJOUTE de nouveaux critères de
recherche et de nouvelles annonces à ce qui existe déjà, sans rien effacer.

Sorties, à chaque exécution (créées si besoin) :
- fixtures/annonces/recherches.csv   -> tous les critères de recherche
- fixtures/annonces/annonces.csv     -> toutes les annonces, à plat
- fixtures/annonces/json/annonce_XXXX.json -> une annonce par fichier JSON

Ce dossier de sortie est ignoré par git (données générées, pas des fixtures
de référence).

Aucune dépendance externe : uniquement la bibliothèque standard.
"""

import argparse
import csv
import json
import os
import random
import re
import string
import uuid
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Référentiels de données
# ---------------------------------------------------------------------------

VILLES = [
    ("Paris", "75000", 48.8566, 2.3522),
    ("Lyon", "69000", 45.7640, 4.8357),
    ("Marseille", "13000", 43.2965, 5.3698),
    ("Toulouse", "31000", 43.6047, 1.4442),
    ("Nice", "06000", 43.7102, 7.2620),
    ("Nantes", "44000", 47.2184, -1.5536),
    ("Strasbourg", "67000", 48.5734, 7.7521),
    ("Bordeaux", "33000", 44.8378, -0.5792),
    ("Lille", "59000", 50.6292, 3.0573),
    ("Rennes", "35000", 48.1173, -1.6778),
    ("Reims", "51100", 49.2583, 4.0317),
    ("Le Havre", "76600", 49.4944, 0.1079),
    ("Saint-Étienne", "42000", 45.4397, 4.3872),
    ("Toulon", "83000", 43.1242, 5.9280),
    ("Grenoble", "38000", 45.1885, 5.7245),
    ("Dijon", "21000", 47.3220, 5.0415),
    ("Angers", "49000", 47.4784, -0.5632),
    ("Annecy", "74000", 45.8992, 6.1294),
    ("Perpignan", "66000", 42.6887, 2.8948),
    ("Limoges", "87000", 45.8336, 1.2611),
]
VILLES_PAR_NOM = {v[0]: v for v in VILLES}

TYPES_BIEN = [
    "Appartement", "Maison", "Studio", "Loft", "Villa",
    "Duplex", "Terrain", "Local commercial", "Chalet", "Château",
]

RUES = [
    "rue de la République", "avenue des Champs", "rue Victor Hugo",
    "boulevard Gambetta", "rue Jean Jaurès", "impasse des Lilas",
    "allée des Platanes", "rue du Commerce", "quai de la Loire",
    "chemin des Vignes", "place de la Mairie", "rue Pasteur",
]

ADJECTIFS = [
    "lumineux", "spacieux", "rénové", "charmant", "atypique",
    "au calme", "avec vue dégagée", "en excellent état", "à rafraîchir",
    "de standing",
]

DPE_LETTRES = ["A", "B", "C", "D", "E", "F", "G"]

CRITERES_LIBRES = [
    "balcon", "jardin", "parking", "ascenseur", "terrasse",
    "cave", "vue", "calme", "lumineux", "piscine",
]

PRENOMS = ["Jean", "Marie", "Ahmed", "Sophie", "Luc", "Claire", "Karim", "Julie", "Marc", "Nadia"]
NOMS = ["Martin", "Bernard", "Dubois", "Moreau", "Lefevre", "Girard", "Fontaine", "Perrin", "Roche", "Faure"]
AGENCES = ["ImmoPlus", "Century Habitat", "Nid Doré", "Clé en Main Immo", "Toit & Vous", "Provence Immobilier"]

# Formateurs de date : permettent d'obtenir des formats variés d'une source à l'autre
def _fmt_iso(d):
    return d.strftime("%Y-%m-%d")


def _fmt_iso_datetime(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def _fmt_fr_slash(d):
    return d.strftime("%d/%m/%Y")


def _fmt_fr_texte(d):
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month - 1]} {d.year}"


def _fmt_timestamp(d):
    return int(d.timestamp())


def _fmt_us(d):
    return d.strftime("%m-%d-%Y")


DATE_FORMATTERS = [_fmt_iso, _fmt_iso_datetime, _fmt_fr_slash, _fmt_fr_texte, _fmt_timestamp, _fmt_us]


def date_aleatoire():
    debut = datetime.now() - timedelta(days=730)
    delta = random.randint(0, 730)
    heure = random.randint(0, 23)
    minute = random.randint(0, 59)
    return debut + timedelta(days=delta, hours=heure, minutes=minute)


def maybe(proba):
    """Retourne True avec la probabilité donnée (0.0 à 1.0)."""
    return random.random() < proba


def generer_montant(type_bien):
    if type_bien == "Terrain":
        return random.randint(500, 20000) * 100
    return random.randint(400, 5000) * 100


# ---------------------------------------------------------------------------
# Génération d'un critère de recherche
# ---------------------------------------------------------------------------

def generer_reference_recherche():
    return "REC-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generer_recherche(id_recherche):
    ville, cp, _, _ = random.choice(VILLES)
    type_bien = random.choice(TYPES_BIEN)

    recherche = {
        "id": id_recherche,
        "reference": generer_reference_recherche(),
        "date_creation": _fmt_iso(date_aleatoire()),
        "ville": ville,
        "code_postal": cp,
        "type_bien": type_bien,
        "budget_max": generer_montant(type_bien),
        "surface_min": random.randint(15, 250),
    }

    if type_bien != "Terrain":
        if maybe(0.7):
            recherche["nb_pieces_min"] = random.randint(1, 6)
        if maybe(0.4):
            recherche["nb_chambres_min"] = random.randint(0, 4)
        if maybe(0.4):
            recherche["dpe_max"] = random.choice(DPE_LETTRES)

    criteres_souhaites = random.sample(CRITERES_LIBRES, k=random.randint(0, 3))
    if criteres_souhaites:
        recherche["criteres_souhaites"] = criteres_souhaites

    return recherche


# ---------------------------------------------------------------------------
# Génération d'une annonce correspondant à un critère de recherche
# ---------------------------------------------------------------------------

def generer_description(type_bien, ville, surface):
    adj = random.choice(ADJECTIFS)
    phrases = [
        f"{type_bien} {adj} de {surface} m² situé à {ville}.",
        "Proche de toutes commodités, transports et écoles.",
        "À visiter sans tarder.",
    ]
    if maybe(0.3):
        phrases.insert(1, "Cave et parking inclus.")
    if maybe(0.2):
        phrases.append("Travaux à prévoir.")
    return " ".join(phrases)


def generer_contact():
    contact = {}
    if maybe(0.6):
        contact["nom"] = f"{random.choice(PRENOMS)} {random.choice(NOMS)}"
    if maybe(0.7):
        contact["telephone"] = "0" + "".join(random.choices(string.digits, k=9))
    if maybe(0.5):
        contact["email"] = (contact.get("nom", "contact").lower().replace(" ", ".")
                             + str(random.randint(1, 99)) + "@example.com")
    if maybe(0.4):
        contact["agence"] = random.choice(AGENCES)
    return contact if contact else None


def generer_reference_annonce():
    return "AN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generer_annonce_correspondante(recherche):
    """Génère une annonce qui correspond au critère de recherche donné.

    Les champs qui définissent la correspondance (ville, type de bien, prix
    borné par le budget, surface au-dessus du minimum demandé) sont toujours
    présents et cohérents. Le reste des champs suit le même modèle
    "source hétérogène" que le générateur d'annonces d'origine : présence,
    nommage et formats variables.
    """
    ville = recherche["ville"]
    cp = recherche["code_postal"]
    _, _, lat, lon = VILLES_PAR_NOM[ville]
    type_bien = recherche["type_bien"]

    surface_min = recherche.get("surface_min", 15)
    surface = random.randint(surface_min, surface_min + 150)

    budget_max = recherche["budget_max"]
    plancher = max(int(budget_max * 0.5), 100)
    prix = random.randint(plancher, budget_max)

    d = date_aleatoire()
    formatteur = random.choice(DATE_FORMATTERS)

    annonce = {
        "id": str(uuid.uuid4()),
        "reference": generer_reference_annonce(),
        "recherche_ref": recherche["reference"],
        "type_bien": type_bien,
        "titre": f"{type_bien} {random.choice(ADJECTIFS)} à {ville}",
        "ville": ville,
        "code_postal": cp,
        "date_publication": formatteur(d),
    }

    annonce["prix"] = f"{prix} €" if maybe(0.15) else prix
    if maybe(0.2):
        annonce["charges_mensuelles"] = round(random.uniform(50, 400), 2)

    if maybe(0.1):
        annonce["surface_m2"] = surface
    else:
        annonce["surface"] = surface

    if type_bien != "Terrain":
        nb_pieces_min = recherche.get("nb_pieces_min")
        if nb_pieces_min:
            annonce["nb_pieces"] = random.randint(nb_pieces_min, nb_pieces_min + 4)
        elif maybe(0.75):
            annonce["nb_pieces"] = random.randint(1, 8)

        nb_chambres_min = recherche.get("nb_chambres_min")
        if nb_chambres_min:
            annonce["nb_chambres"] = random.randint(nb_chambres_min, nb_chambres_min + 3)
        elif maybe(0.5):
            annonce["nb_chambres"] = random.randint(0, 5)

        if maybe(0.4):
            annonce["etage"] = random.choice(["RDC", 0, 1, 2, 3, 4, 5, "dernier étage"])
        if maybe(0.3):
            annonce["meuble"] = random.choice([True, False])

        dpe_max = recherche.get("dpe_max")
        if dpe_max and maybe(0.85):
            idx_max = DPE_LETTRES.index(dpe_max)
            annonce["dpe"] = random.choice(DPE_LETTRES[: idx_max + 1])
        elif maybe(0.35):
            annonce["dpe"] = random.choice(DPE_LETTRES)

        if maybe(0.25):
            annonce["annee_construction"] = random.randint(1850, 2024)

    if maybe(0.5):
        annonce["adresse"] = f"{random.randint(1, 200)} {random.choice(RUES)}"

    if maybe(0.5):
        annonce["latitude"] = round(lat + random.uniform(-0.05, 0.05), 6)
        annonce["longitude"] = round(lon + random.uniform(-0.05, 0.05), 6)

    if maybe(0.8):
        annonce["description"] = generer_description(type_bien, ville, surface)

    for critere in recherche.get("criteres_souhaites", []):
        if maybe(0.85):
            annonce[critere] = True

    contact = generer_contact()
    if contact:
        annonce["contact"] = contact

    if maybe(0.3):
        annonce["photos"] = [
            f"https://exemple-images.test/{annonce['reference']}/{i}.jpg"
            for i in range(1, random.randint(1, 6))
        ]

    if maybe(0.15):
        annonce["particulier"] = True
    elif maybe(0.5):
        annonce["exclusivite"] = maybe(0.5)

    return annonce


# ---------------------------------------------------------------------------
# Export CSV (aplatissement + accumulation entre exécutions)
# ---------------------------------------------------------------------------

def aplatir(d, prefixe=""):
    lignes = {}
    for cle, valeur in d.items():
        chemin = f"{prefixe}{cle}"
        if isinstance(valeur, dict):
            lignes.update(aplatir(valeur, prefixe=f"{chemin}."))
        elif isinstance(valeur, list):
            lignes[chemin] = "; ".join(str(v) for v in valeur)
        else:
            lignes[chemin] = valeur
    return lignes


def lire_csv_existant(chemin):
    if not os.path.exists(chemin):
        return []
    with open(chemin, "r", newline="", encoding="utf-8-sig") as f:
        return [dict(ligne) for ligne in csv.DictReader(f)]


def ecrire_csv_cumulatif(lignes_existantes, nouvelles_lignes_aplaties, chemin_csv):
    toutes_les_lignes = lignes_existantes + nouvelles_lignes_aplaties

    colonnes = []
    vues = set()
    for ligne in toutes_les_lignes:
        for cle in ligne:
            if cle not in vues:
                vues.add(cle)
                colonnes.append(cle)

    with open(chemin_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colonnes, restval="")
        writer.writeheader()
        for ligne in toutes_les_lignes:
            writer.writerow(ligne)


def prochain_id_recherche(recherches_existantes):
    max_id = 0
    for ligne in recherches_existantes:
        try:
            max_id = max(max_id, int(ligne.get("id", 0)))
        except (TypeError, ValueError):
            continue
    return max_id + 1


def prochain_index_json(dossier_json):
    max_index = 0
    if os.path.isdir(dossier_json):
        for nom in os.listdir(dossier_json):
            correspondance = re.match(r"annonce_(\d+)\.json$", nom)
            if correspondance:
                max_index = max(max_index, int(correspondance.group(1)))
    return max_index + 1


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Génère des critères de recherche et des annonces immobilières "
                     "factices correspondantes (JSON + CSV). Chaque exécution ajoute "
                     "de nouvelles données à celles déjà générées."
    )
    parser.add_argument("-r", "--nombre-recherches", type=int, default=5,
                         help="Nombre de nouveaux critères de recherche à générer (défaut : 5).")
    parser.add_argument("--min-annonces", type=int, default=100,
                         help="Nombre minimum d'annonces générées par recherche (défaut : 1).")
    parser.add_argument("--max-annonces", type=int, default=1000,
                         help="Nombre maximum d'annonces générées par recherche (défaut : 4).")
    args = parser.parse_args()

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dossier_fixtures = os.path.join(racine, "fixtures", "annonces")
    dossier_json = os.path.join(dossier_fixtures, "json")
    chemin_csv_recherches = os.path.join(dossier_fixtures, "recherches.csv")
    chemin_csv_annonces = os.path.join(dossier_fixtures, "annonces.csv")

    os.makedirs(dossier_json, exist_ok=True)

    recherches_existantes = lire_csv_existant(chemin_csv_recherches)
    annonces_existantes = lire_csv_existant(chemin_csv_annonces)

    id_suivant = prochain_id_recherche(recherches_existantes)
    index_json_suivant = prochain_index_json(dossier_json)

    nouvelles_recherches = []
    nouvelles_annonces = []

    for i in range(args.nombre_recherches):
        recherche = generer_recherche(id_suivant + i)
        nouvelles_recherches.append(recherche)

        nb_annonces = random.randint(args.min_annonces, args.max_annonces)
        for _ in range(nb_annonces):
            nouvelles_annonces.append(generer_annonce_correspondante(recherche))

    for annonce in nouvelles_annonces:
        chemin_fichier = os.path.join(dossier_json, f"annonce_{index_json_suivant:04d}.json")
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(annonce, f, ensure_ascii=False, indent=2)
        index_json_suivant += 1

    ecrire_csv_cumulatif(recherches_existantes, [aplatir(r) for r in nouvelles_recherches], chemin_csv_recherches)
    ecrire_csv_cumulatif(annonces_existantes, [aplatir(a) for a in nouvelles_annonces], chemin_csv_annonces)

    print(f"{len(nouvelles_recherches)} nouveaux critères de recherche générés "
          f"(total cumulé : {len(recherches_existantes) + len(nouvelles_recherches)}).")
    print(f"{len(nouvelles_annonces)} nouvelles annonces générées "
          f"(total cumulé : {len(annonces_existantes) + len(nouvelles_annonces)}).")
    print(f"  Recherches CSV : {chemin_csv_recherches}")
    print(f"  Annonces  CSV : {chemin_csv_annonces}")
    print(f"  Annonces JSON : {dossier_json}")


if __name__ == "__main__":
    main()
