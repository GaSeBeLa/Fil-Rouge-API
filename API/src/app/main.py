"""
main.py — Point d'entrée de l'API FastAPI.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Ce fichier ne fait plus que créer l'application FastAPI et y brancher un
router par table (voir routes/). Le détail de chaque route (GET liste,
GET/{id}, POST, PUT/{id}, DELETE/{id}) vit désormais dans trois couches
séparées, dans l'ordre où une requête les traverse :

    routes/<table>_router.py        → HTTP : reçoit la requête, traduit les
                                      erreurs métier en codes HTTP (404, 409)
    services/<table>_service.py    → métier : c'est ici qu'irait une règle
                                      comme "hasher le mot de passe avant de
                                      créer un User" (pas encore nécessaire
                                      aujourd'hui, mais l'emplacement existe)
    repositories/<table>_repository.py → données : parle à la Session
                                      SQLModel/PostgreSQL, rien d'autre

Chacune de ces trois couches hérite d'une classe de base générique
(routes/crud_router.py, services/base_service.py,
repositories/base_repository.py) qui porte le comportement CRUD commun aux
11 tables — évite de le dupliquer 11 fois, comme le faisaient déjà
list_all/get_one_or_404/create_one/... dans l'ancienne version de ce
fichier.

Il n'y a volontairement pas de PATCH (mise à jour partielle) : PUT
remplace toute la ligne (sémantique REST standard), plus simple à
raisonner pour un projet de cette taille.

Lancer l'API en développement (depuis le dossier API/) :
    uvicorn src.app.main:app --reload

Puis ouvrir http://localhost:8000/docs : FastAPI génère automatiquement
une interface interactive (Swagger UI) pour tester chaque route sans rien
écrire — pratique pour explorer et pour ta démonstration.
============================================================================
"""

from fastapi import FastAPI

from .routes import (
    client_router,
    criteria_router,
    estate_proposed_router,
    estate_router,
    estate_search_request_router,
    hunter_router,
    mandate_router,
    picture_router,
    real_estate_manager_router,
    role_router,
    search_request_router,
    user_router,
)

app = FastAPI(
    title="Fil Rouge Immobilier — API",
    description="API du service de chasse immobilière (projet fil rouge EISI Data-IA).",
    version="0.1.0",
)


@app.get("/", tags=["health"])
def health_check():
    """
    Route de vérification basique : confirme que l'API répond, sans
    toucher à la base. Utile pour vérifier rapidement que le serveur
    tourne, avant même de tester la connexion à PostgreSQL.
    """
    return {"status": "ok", "message": "L'API Fil Rouge Immobilier tourne."}


app.include_router(user_router.router)
app.include_router(role_router.router)
app.include_router(hunter_router.router)
app.include_router(client_router.router)
app.include_router(real_estate_manager_router.router)
app.include_router(search_request_router.router)
app.include_router(criteria_router.router)
app.include_router(mandate_router.router)
app.include_router(estate_router.router)
app.include_router(estate_proposed_router.router)
app.include_router(estate_search_request_router.router)
app.include_router(picture_router.router)
