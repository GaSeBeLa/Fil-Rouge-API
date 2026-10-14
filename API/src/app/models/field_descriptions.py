"""
field_descriptions.py — Les phrases du Swagger sous les id de compte.

`id_client`, `id_hunter`, `id_realestatemanager` et `id_author` portent le
numéro du COMPTE (`user.id`), pas l'`id` de la table de profil : `client`,
`hunter` et `real_estate_manager` ont chacune le leur, et les confondre
vise la mauvaise ligne (piège soulevé par Gabriel le 2026-10-14 ; fiche FIN2).
Une phrase par champ, partagée par tous les modèles qui le portent.
"""

CLIENT_ACCOUNT = "Numéro du compte (`user.id`) du client, pas `client.id`."
HUNTER_ACCOUNT = "Numéro du compte (`user.id`) du chasseur, pas `hunter.id`."
MANAGER_ACCOUNT = "Numéro du compte (`user.id`) du manager, pas `real_estate_manager.id`."
AUTHOR_ACCOUNT = "Numéro du compte (`user.id`) de l'auteur."
