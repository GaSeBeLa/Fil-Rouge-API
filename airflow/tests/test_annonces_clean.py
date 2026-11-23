"""Tests de airflow/src/annonces/clean.py : une règle de normalised.py par test."""
from __future__ import annotations

from datetime import date

import pytest

from src.annonces.clean import ESTATE_COLUMNS, KEY, clean_annonce, parse_date, parse_floor, parse_price_eur


def _raw(**fields: str) -> dict[str, object]:
    """Une annonce brute minimale, comme une ligne de annonces.csv."""
    row: dict[str, object] = {"reference": "AN-TEST0001", "type_bien": "Maison", "ville": "Toulouse",
                              "code_postal": "31000", "surface": "100", "prix": "250000"}
    row.update(fields)
    return row


@pytest.mark.parametrize(("raw", "expected"), [
    ("406042 €", 406042),
    ("354712", 354712),
    ("406 042 €", 406042),
    ("406 042 €", 406042),
    ("", None),
    ("n/c", None),
])
def test_price_is_whole_euros(raw, expected):
    assert parse_price_eur(raw) == expected


def test_price_stays_in_euros_not_k_euros():
    # Le schéma v3 range le prix en euros (price INTEGER) : 354712, jamais 354.7.
    assert clean_annonce(_raw(prix="354712"))["price"] == 354712


@pytest.mark.parametrize(("raw", "expected"), [
    ("1785807730", date(2026, 8, 4)),
    ("2025-06-06T12:43:10", date(2025, 6, 6)),
    ("2025-03-19", date(2025, 3, 19)),
    ("25 octobre 2024", date(2024, 10, 25)),
    ("27/03/2025", date(2025, 3, 27)),
    ("03-16-2026", date(2026, 3, 16)),
    ("hier", None),
    ("", None),
])
def test_publication_date_formats(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("RDC", "0"), ("3", "3"), ("9", "9"), ("10", "10 and more"), ("14", "10 and more"),
    ("dernier étage", "last floor"), ("", None), ("mezzanine", None),
])
def test_floor_follows_the_check_list(raw, expected):
    assert parse_floor(raw) == expected


def test_surface_falls_back_on_surface_m2():
    assert clean_annonce(_raw(surface="", surface_m2="87,5"))["surface"] == 87.5


def test_presence_booleans_empty_means_false():
    row = clean_annonce(_raw(jardin="True", cave="", balcon="True", terrasse=""))
    assert (row["has_garden"], row["has_cellar"], row["nb_balcony"], row["nb_terrace"]) == (True, False, 1, 0)


def test_reference_is_the_key():
    assert clean_annonce(_raw(reference="  AN-RMM28R0H "))[KEY] == "AN-RMM28R0H"


def test_address_split_into_number_and_street():
    row = clean_annonce(_raw(adresse="200 avenue des Champs"))
    assert (row["street_number"], row["street"]) == ("200", "avenue des Champs")


def test_text_derived_columns():
    row = clean_annonce(_raw(titre="Vue dégagée", description="Cave et parking inclus. Travaux à prévoir."))
    assert (row["has_view"], row["parking_spaces"], row["needs_renovation"]) == (True, 1, True)


def test_construction_year_becomes_first_of_january():
    assert clean_annonce(_raw(annee_construction="1888"))["construction_date"] == date(1888, 1, 1)


def test_dpe_letter_goes_to_energy_class_and_country_is_fr():
    row = clean_annonce(_raw(dpe="c"))
    assert (row["energy_class"], row["country_iso"]) == ("C", "FR")


def _contact(**fields: str) -> dict[str, object]:
    """La ligne nettoyée d'une annonce brute portant ces colonnes contact.*."""
    return clean_annonce(_raw(**fields))


def _contact_of(row: dict[str, object]) -> dict[str, object]:
    """Le contact de la ligne ; échoue s'il est absent (None)."""
    contact = row["contact"]
    assert isinstance(contact, dict)
    return contact


FULL_CONTACT = {"contact.nom": "Claire Martin", "contact.telephone": "0453775236",
                "contact.email": "c@example.com", "contact.agence": "Nid Doré", "particulier": "True"}


def test_full_contact_follows_the_estate():
    row = _contact(**FULL_CONTACT)
    assert row["contact"] == {"is_private": True, "agency_name": "Nid Doré", "contact_name": "Claire Martin",
                              "phone_number": "+33453775236", "email": "c@example.com"}
    assert row["_contact_fields_dropped"] == 0


def test_contact_never_enters_estate_columns():
    # Le contact voyage à côté du bien, jamais dans les colonnes de estate.
    assert "contact" not in ESTATE_COLUMNS


def test_no_contact_when_the_four_fields_are_empty():
    row = _contact(**{"contact.nom": " ", "contact.telephone": "", "particulier": "True"})
    assert row["contact"] is None
    assert row["_contact_fields_dropped"] == 0


def test_no_contact_when_every_given_field_is_dirty():
    # Un seul email, mal formé : vidé, il ne reste rien. Une fiche aux quatre
    # champs vides serait refusée par ck_estate_contact_not_empty (init-v3/01).
    row = _contact(**{"contact.email": "pas-un-mail", "particulier": "True"})
    assert row["contact"] is None
    assert row["_contact_fields_dropped"] == 1


def test_blank_field_becomes_none():
    contact = _contact_of(_contact(**{"contact.nom": "  ", "contact.agence": "Nid Doré"}))
    assert (contact["contact_name"], contact["agency_name"]) == (None, "Nid Doré")


def test_is_private_is_never_empty():
    contact = _contact_of(_contact(**{"contact.agence": "Nid Doré"}))
    assert contact["is_private"] is False


def test_dirty_phone_is_dropped_alone():
    row = _contact(**{**FULL_CONTACT, "contact.telephone": "04-53"})
    contact = _contact_of(row)
    assert (contact["phone_number"], contact["contact_name"]) == (None, "Claire Martin")
    assert row["_contact_fields_dropped"] == 1


def test_international_phone_is_kept():
    contact = _contact_of(_contact(**{**FULL_CONTACT, "contact.telephone": "+33453775236"}))
    assert contact["phone_number"] == "+33453775236"


def test_dirty_email_and_long_name_are_dropped_and_counted():
    row = _contact(**{**FULL_CONTACT, "contact.email": "pas-un-email", "contact.nom": "x" * 101})
    contact = _contact_of(row)
    assert (contact["email"], contact["contact_name"]) == (None, None)
    assert row["_contact_fields_dropped"] == 2


def test_output_has_every_estate_column():
    assert set(ESTATE_COLUMNS) <= set(clean_annonce(_raw()))


def test_clean_is_idempotent():
    raw = _raw(prix="406042 €", date_publication="25 octobre 2024", etage="RDC")
    assert clean_annonce(raw) == clean_annonce(dict(raw))
