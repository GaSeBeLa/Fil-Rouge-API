"""
field_descriptions.py — Les phrases du Swagger sous les id de fiche et de compte.

Depuis le chantier PRF (2026-10-15), `id_client`, `id_hunter` et
`id_realestatemanager` portent le numéro de la FICHE (`client.id`,
`hunter.id`, `real_estate_manager.id`), pas le numéro du compte : les
confondre vise la mauvaise ligne (piège soulevé par Gabriel le 2026-10-14 ;
fiche FIN2). `id_author`, lui, porte le numéro du compte (`user.id`).
Une phrase par champ, partagée par tous les modèles qui le portent.

L'autre bout du même piège : dans `client`, `hunter` et `real_estate_manager`,
`id` est le numéro de la fiche, celui que les autres tables citent, et
`id_user` le numéro du compte (soulevé par Laurence le 2026-10-14).
`{item_id}` de leurs routes vise `id`.
"""

CLIENT_PROFILE = "Numéro de la fiche client (`client.id`), pas le numéro du compte (`user.id`)."
HUNTER_PROFILE = "Numéro de la fiche chasseur (`hunter.id`), pas le numéro du compte (`user.id`)."
MANAGER_PROFILE = "Numéro de la fiche manager (`real_estate_manager.id`), pas le numéro du compte (`user.id`)."
AUTHOR_ACCOUNT = "Numéro du compte (`user.id`) de l'auteur."

CLIENT_ID = "Numéro de la fiche client : c'est lui que citent les `id_client` des autres tables."
HUNTER_ID = "Numéro de la fiche chasseur : c'est lui que citent les `id_hunter` des autres tables."
MANAGER_ID = "Numéro de la fiche manager : c'est lui que citent les `id_realestatemanager` des autres tables."
CLIENT_USER = "Numéro du compte (`user.id`) du client. Les autres tables citent la fiche (`id`), pas ce numéro."
HUNTER_USER = "Numéro du compte (`user.id`) du chasseur. Les autres tables citent la fiche (`id`), pas ce numéro."
MANAGER_USER = "Numéro du compte (`user.id`) du manager. Les autres tables citent la fiche (`id`), pas ce numéro."
