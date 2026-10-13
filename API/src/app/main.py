"""
main.py — Point d'entrée de l'API FastAPI.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Ce fichier ne fait plus que créer l'application FastAPI et y brancher un
router par table (voir routes/). Le détail de chaque route (GET liste,
GET/{id}, POST, PUT/{id} ; plus de DELETE, ADR-049) vit désormais dans trois couches
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
19 tables — évite de le dupliquer 11 fois, comme le faisaient déjà
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

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .routes import (
    auth_router,
    client_router,
    criteria_router,
    estate_proposed_router,
    estate_router,
    estate_search_request_router,
    hunter_router,
    mandate_router,
    picture_router,
    real_estate_manager_router,
    review_media_router,
    role_router,
    search_request_router,
    signup_router,
    user_router,
    sale_router,
    commission_scale_router,
    payment_router,
    hunter_performance_router,
    parameters_fees_router,
    hunter_rate_parameters_router,
    visit_router,
)

# Doc Swagger (/docs) : la description de l'API et une phrase par section,
# écrites pour qui découvre le projet. L'ordre de la liste est celui des
# sections à l'écran : du compte au paiement, comme le parcours d'un client.
OPENAPI_DESCRIPTION = """
API du service de chasse immobilière (projet fil rouge EISI Data-IA).

**Pour commencer** :

1. **Authorize** → `APIKeyHeader` : la clé d'API (`API_KEY_INTERNAL` de `docker/.env`).
2. `POST /auth/login` avec votre email et votre mot de passe : copier `access_token`.
3. **Authorize** → `HTTPBearer` : coller le jeton seul, sans le mot `Bearer`.

Chaque table a les mêmes routes : lister, lire par `id`, créer, modifier.
Aucune ne supprime : un `DELETE` répond `405` (ADR-049).
Le guide complet est dans `API/README.md`.
"""

OPENAPI_TAGS = [
    {"name": "health", "description": "Vérifier que le serveur répond."},
    {"name": "auth", "description": "Se connecter : recevoir le jeton que demandent les autres routes."},
    {"name": "search-requests", "description": "Le formulaire du site : un visiteur sans compte dépose sa demande."},
    {"name": "user", "description": "Les comptes de connexion (email, mot de passe, rôle). `Admin` seul écrit."},
    {"name": "role", "description": "Les cinq rôles : `Admin`, `Client`, `Hunter`, `Manager`, `Reader`."},
    {"name": "hunter", "description": "Les chasseurs : ils cherchent des biens pour leurs clients."},
    {"name": "client", "description": "Les clients : les personnes qui cherchent un bien."},
    {"name": "real_estate_manager", "description": "Les managers : ils encadrent des chasseurs."},
    {"name": "search_request", "description": "Les demandes de recherche d'un client."},
    {"name": "criteria", "description": "Les critères d'une demande (budget, surface…). Chaque révision garde la précédente."},
    {"name": "mandate", "description": "Les mandats : le contrat qui lie un client et un chasseur."},
    {"name": "estate", "description": "Les biens immobiliers (annonces)."},
    {"name": "estate_searchrequest", "description": "Les biens retenus par le chasseur pour une demande, avec son avis."},
    {"name": "review_media", "description": "Les fichiers audio ou vidéo joints à l'avis du chasseur."},
    {"name": "picture", "description": "Les photos d'un bien."},
    {"name": "estate_proposed", "description": "Les biens proposés au client, et le suivi de l'offre."},
    {"name": "visit", "description": "Les visites d'un bien."},
    {"name": "sale", "description": "Les ventes. `POST /sales/{id}/payment` calcule la commission du chasseur."},
    {"name": "payment", "description": "Les paiements du chasseur : `announced` → `scheduled` → `paid`, ou `refused`."},
    {"name": "parameters_fees", "description": "Les honoraires de l'agence (part fixe et pourcentage), par version datée."},
    {"name": "commission_scale", "description": "Le barème : tranche de prix → taux de commission du chasseur."},
    {"name": "hunter_rate_parameters", "description": "Les réglages qui ajustent le taux du chasseur (ancienneté, performance)."},
    {"name": "hunter_performance", "description": "Le journal des notes du chasseur. L'API l'écrit seule, au paiement."},
]

app = FastAPI(
    title="Fil Rouge Immobilier — API",
    description=OPENAPI_DESCRIPTION,
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Le 422 de FastAPI, sans recopier le corps reçu (`input`) : un NaN qu'il
    contiendrait ne s'écrit pas en JSON, et la réponse 422 devenait un 500.
    Le client a déjà ce corps : c'est lui qui l'a envoyé.
    """
    errors = [{key: value for key, value in error.items() if key != "input"} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


@app.get("/", tags=["health"], summary="Vérifier que l'API répond")
def health_check():
    """
    Confirme que l'API tourne, sans toucher à la base. Ouverte à tous :
    ni clé d'API, ni jeton. Si elle répond `200`, le serveur est debout ;
    la base, elle, n'est pas testée ici.
    """
    return {"status": "ok", "message": "L'API Fil Rouge Immobilier tourne."}


# ADR-052 : connexion par jeton JWT, exigé par toutes les routes CRUD (fiche API2).
app.include_router(auth_router.router)
# P5 : demande déposée avant le compte — clé d'API, pas de jeton (fiche API9).
app.include_router(signup_router.router)
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
app.include_router(review_media_router.router)
app.include_router(picture_router.router)
app.include_router(visit_router.router)
app.include_router(sale_router.router)
app.include_router(parameters_fees_router.router)
app.include_router(commission_scale_router.router)
app.include_router(payment_router.router)
app.include_router(hunter_performance_router.router)
# Q-REM-05 : les réglages du calcul de rémunération, versionnés.
app.include_router(hunter_rate_parameters_router.router)
