"""
field_descriptions.py — Les phrases du Swagger sous les id de compte.

`id_client`, `id_hunter`, `id_realestatemanager` et `id_author` portent le
numéro du COMPTE (`user.id`), pas l'`id` de la table de profil : `client`,
`hunter` et `real_estate_manager` ont chacune le leur, et les confondre
vise la mauvaise ligne (piège soulevé par Gabriel le 2026-10-14 ; fiche FIN2).
Une phrase par champ, partagée par tous les modèles qui le portent.

L'autre bout du même piège : dans `client`, `hunter` et `real_estate_manager`,
`id` est l'id technique de la fiche, `id_user` le numéro du compte que les
autres tables citent (soulevé par Laurence le 2026-10-14). `{item_id}` de
leurs routes vise `id`.
"""

CLIENT_ACCOUNT = "Numéro du compte (`user.id`) du client, pas `client.id`."
HUNTER_ACCOUNT = "Numéro du compte (`user.id`) du chasseur, pas `hunter.id`."
MANAGER_ACCOUNT = "Numéro du compte (`user.id`) du manager, pas `real_estate_manager.id`."
AUTHOR_ACCOUNT = "Numéro du compte (`user.id`) de l'auteur."

CLIENT_ID = "Id technique de la fiche client. Les autres tables ne le citent pas : leur `id_client` vaut `id_user`."
HUNTER_ID = "Id technique de la fiche chasseur. Les autres tables ne le citent pas : leur `id_hunter` vaut `id_user`."
MANAGER_ID = (
    "Id technique de la fiche manager. Les autres tables ne le citent pas : "
    "leur `id_realestatemanager` vaut `id_user`."
)
CLIENT_USER = "Numéro du compte (`user.id`) du client : c'est lui que portent les `id_client` des autres tables."
HUNTER_USER = "Numéro du compte (`user.id`) du chasseur : c'est lui que portent les `id_hunter` des autres tables."
MANAGER_USER = (
    "Numéro du compte (`user.id`) du manager : c'est lui que portent les `id_realestatemanager` des autres tables."
)
