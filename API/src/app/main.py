"""
main.py — Point d'entrée de l'API FastAPI.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Ce fichier définit les "routes" (les adresses HTTP que l'API expose,
comme /users ou /mandates) et ce que chacune doit faire quand on l'appelle.

Pour chaque table : GET (liste), GET/{id}, POST, PUT/{id}, DELETE/{id}.
Le circuit complet : navigateur/Tabularis/curl -> FastAPI -> SQLModel ->
PostgreSQL -> retour.

Il n'y a volontairement pas de PATCH (mise à jour partielle) : PUT
remplace toute la ligne (sémantique REST standard), plus simple à
raisonner pour un projet de cette taille. Il n'y a pas non plus de
logique métier (qui a le droit de faire quoi, quelles validations
avant d'atteindre la base...) : à ajouter plus tard si besoin.

Lancer l'API en développement (depuis le dossier API2/) :
    uvicorn src.app.main:app --reload

Puis ouvrir http://localhost:8000/docs : FastAPI génère automatiquement
une interface interactive (Swagger UI) pour tester chaque route sans rien
écrire — pratique pour explorer et pour ta démonstration.
============================================================================
"""

from typing import List

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .database import get_session
from .models import (
    Client,
    Criteria,
    Estate,
    EstateProposed,
    EstateSearchRequest,
    Hunter,
    Mandate,
    Picture,
    RealEstateManager,
    SearchRequest,
    User,
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


# ============================================================================
# UTILITAIRES PARTAGÉS — pour éviter de répéter la même logique 11 fois
# ============================================================================

def list_all(model, session: Session):
    """
    Retourne toutes les lignes d'une table. `select(model)` construit la
    requête SQL équivalente à `SELECT * FROM <table>`, `session.exec(...)`
    l'exécute, `.all()` récupère tous les résultats en mémoire.

    Volontairement simple pour l'instant (pas de pagination) : à
    améliorer avant une vraie mise en production, où renvoyer des
    milliers de lignes d'un coup serait problématique.
    """
    return session.exec(select(model)).all()


def get_one_or_404(model, item_id: int, session: Session, not_found_detail: str):
    """
    Récupère une ligne par sa clé primaire, ou lève une 404 sinon.
    Centralise ce que chaque route GET/{id}, PUT/{id} et DELETE/{id} fait
    en premier : aller chercher la ligne avant de travailler dessus.
    """
    item = session.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return item


def create_one(item, session: Session):
    """
    Insère une nouvelle ligne. `item.id` est toujours réinitialisé à
    None avant l'insertion : en base, "id" est une colonne GENERATED
    ALWAYS AS IDENTITY, PostgreSQL refuse qu'on lui donne une valeur
    explicite sans la syntaxe spéciale OVERRIDING SYSTEM VALUE (réservée
    aux scripts de migration, voir 02_migration.sql).
    """
    item.id = None
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Contrainte violée (valeur en double ou référence inexistante).",
        ) from exc
    session.refresh(item)
    return item


def replace_one(existing, data, session: Session):
    """
    Remplace le contenu d'une ligne existante par celui de `data` (toutes
    les colonnes sauf "id", qui reste celle de l'URL, pas celle du
    corps de la requête). Sémantique PUT : remplacement complet de la
    ligne, pas de fusion partielle façon PATCH.
    """
    for key, value in data.model_dump(exclude={"id"}).items():
        setattr(existing, key, value)
    session.add(existing)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Contrainte violée (valeur en double ou référence inexistante).",
        ) from exc
    session.refresh(existing)
    return existing


def delete_one(existing, session: Session):
    """
    Supprime une ligne. Toutes les FK du schéma sont en ON DELETE
    RESTRICT (voir create_fil_rouge_immobilier.sql) : si d'autres lignes
    pointent encore vers celle-ci, PostgreSQL refuse la suppression, et
    on transforme ça en 409 plutôt que de laisser planter en 500.
    Renvoie la ligne supprimée, pratique pour confirmer ce qui a
    disparu depuis Swagger UI.
    """
    session.delete(existing)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Suppression impossible : cette ligne est encore référencée ailleurs.",
        ) from exc
    return existing


# ============================================================================
# ROUTES — GET liste / GET par id / POST / PUT / DELETE, une table à la fois
# ============================================================================

# ----------------------------------------------------------------------
# USER
# ----------------------------------------------------------------------
@app.get("/users", response_model=List[User], tags=["user"])
def get_users(session: Session = Depends(get_session)):
    return list_all(User, session)


@app.get("/users/{user_id}", response_model=User, tags=["user"])
def get_user(user_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(User, user_id, session, "Utilisateur introuvable")


@app.post("/users", response_model=User, status_code=201, tags=["user"])
def create_user(user: User, session: Session = Depends(get_session)):
    return create_one(user, session)


@app.put("/users/{user_id}", response_model=User, tags=["user"])
def update_user(user_id: int, data: User, session: Session = Depends(get_session)):
    user = get_one_or_404(User, user_id, session, "Utilisateur introuvable")
    return replace_one(user, data, session)


@app.delete("/users/{user_id}", response_model=User, tags=["user"])
def delete_user(user_id: int, session: Session = Depends(get_session)):
    user = get_one_or_404(User, user_id, session, "Utilisateur introuvable")
    return delete_one(user, session)


# ----------------------------------------------------------------------
# HUNTER
# ----------------------------------------------------------------------
@app.get("/hunters", response_model=List[Hunter], tags=["hunter"])
def get_hunters(session: Session = Depends(get_session)):
    return list_all(Hunter, session)


@app.get("/hunters/{hunter_id}", response_model=Hunter, tags=["hunter"])
def get_hunter(hunter_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(Hunter, hunter_id, session, "Chasseur introuvable")


@app.post("/hunters", response_model=Hunter, status_code=201, tags=["hunter"])
def create_hunter(hunter: Hunter, session: Session = Depends(get_session)):
    return create_one(hunter, session)


@app.put("/hunters/{hunter_id}", response_model=Hunter, tags=["hunter"])
def update_hunter(hunter_id: int, data: Hunter, session: Session = Depends(get_session)):
    hunter = get_one_or_404(Hunter, hunter_id, session, "Chasseur introuvable")
    return replace_one(hunter, data, session)


@app.delete("/hunters/{hunter_id}", response_model=Hunter, tags=["hunter"])
def delete_hunter(hunter_id: int, session: Session = Depends(get_session)):
    hunter = get_one_or_404(Hunter, hunter_id, session, "Chasseur introuvable")
    return delete_one(hunter, session)


# ----------------------------------------------------------------------
# CLIENT
# ----------------------------------------------------------------------
@app.get("/clients", response_model=List[Client], tags=["client"])
def get_clients(session: Session = Depends(get_session)):
    return list_all(Client, session)


@app.get("/clients/{client_id}", response_model=Client, tags=["client"])
def get_client(client_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(Client, client_id, session, "Client introuvable")


@app.post("/clients", response_model=Client, status_code=201, tags=["client"])
def create_client(client: Client, session: Session = Depends(get_session)):
    return create_one(client, session)


@app.put("/clients/{client_id}", response_model=Client, tags=["client"])
def update_client(client_id: int, data: Client, session: Session = Depends(get_session)):
    client = get_one_or_404(Client, client_id, session, "Client introuvable")
    return replace_one(client, data, session)


@app.delete("/clients/{client_id}", response_model=Client, tags=["client"])
def delete_client(client_id: int, session: Session = Depends(get_session)):
    client = get_one_or_404(Client, client_id, session, "Client introuvable")
    return delete_one(client, session)


# ----------------------------------------------------------------------
# REAL_ESTATE_MANAGER
# ----------------------------------------------------------------------
@app.get("/real-estate-managers", response_model=List[RealEstateManager], tags=["real_estate_manager"])
def get_real_estate_managers(session: Session = Depends(get_session)):
    return list_all(RealEstateManager, session)


@app.get("/real-estate-managers/{manager_id}", response_model=RealEstateManager, tags=["real_estate_manager"])
def get_real_estate_manager(manager_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(RealEstateManager, manager_id, session, "Gestionnaire immobilier introuvable")


@app.post("/real-estate-managers", response_model=RealEstateManager, status_code=201, tags=["real_estate_manager"])
def create_real_estate_manager(manager: RealEstateManager, session: Session = Depends(get_session)):
    return create_one(manager, session)


@app.put("/real-estate-managers/{manager_id}", response_model=RealEstateManager, tags=["real_estate_manager"])
def update_real_estate_manager(manager_id: int, data: RealEstateManager, session: Session = Depends(get_session)):
    manager = get_one_or_404(RealEstateManager, manager_id, session, "Gestionnaire immobilier introuvable")
    return replace_one(manager, data, session)


@app.delete("/real-estate-managers/{manager_id}", response_model=RealEstateManager, tags=["real_estate_manager"])
def delete_real_estate_manager(manager_id: int, session: Session = Depends(get_session)):
    manager = get_one_or_404(RealEstateManager, manager_id, session, "Gestionnaire immobilier introuvable")
    return delete_one(manager, session)


# ----------------------------------------------------------------------
# SEARCH_REQUEST
# ----------------------------------------------------------------------
@app.get("/search-requests", response_model=List[SearchRequest], tags=["search_request"])
def get_search_requests(session: Session = Depends(get_session)):
    return list_all(SearchRequest, session)


@app.get("/search-requests/{search_request_id}", response_model=SearchRequest, tags=["search_request"])
def get_search_request(search_request_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(SearchRequest, search_request_id, session, "Demande de recherche introuvable")


@app.post("/search-requests", response_model=SearchRequest, status_code=201, tags=["search_request"])
def create_search_request(search_request: SearchRequest, session: Session = Depends(get_session)):
    return create_one(search_request, session)


@app.put("/search-requests/{search_request_id}", response_model=SearchRequest, tags=["search_request"])
def update_search_request(search_request_id: int, data: SearchRequest, session: Session = Depends(get_session)):
    search_request = get_one_or_404(SearchRequest, search_request_id, session, "Demande de recherche introuvable")
    return replace_one(search_request, data, session)


@app.delete("/search-requests/{search_request_id}", response_model=SearchRequest, tags=["search_request"])
def delete_search_request(search_request_id: int, session: Session = Depends(get_session)):
    search_request = get_one_or_404(SearchRequest, search_request_id, session, "Demande de recherche introuvable")
    return delete_one(search_request, session)


# ----------------------------------------------------------------------
# CRITERIA
# ----------------------------------------------------------------------
@app.get("/criteria", response_model=List[Criteria], tags=["criteria"])
def get_criteria_list(session: Session = Depends(get_session)):
    return list_all(Criteria, session)


@app.get("/criteria/{criteria_id}", response_model=Criteria, tags=["criteria"])
def get_criteria(criteria_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(Criteria, criteria_id, session, "Critères introuvables")


@app.post("/criteria", response_model=Criteria, status_code=201, tags=["criteria"])
def create_criteria(criteria: Criteria, session: Session = Depends(get_session)):
    return create_one(criteria, session)


@app.put("/criteria/{criteria_id}", response_model=Criteria, tags=["criteria"])
def update_criteria(criteria_id: int, data: Criteria, session: Session = Depends(get_session)):
    criteria = get_one_or_404(Criteria, criteria_id, session, "Critères introuvables")
    return replace_one(criteria, data, session)


@app.delete("/criteria/{criteria_id}", response_model=Criteria, tags=["criteria"])
def delete_criteria(criteria_id: int, session: Session = Depends(get_session)):
    criteria = get_one_or_404(Criteria, criteria_id, session, "Critères introuvables")
    return delete_one(criteria, session)


# ----------------------------------------------------------------------
# MANDATE
# ----------------------------------------------------------------------
@app.get("/mandates", response_model=List[Mandate], tags=["mandate"])
def get_mandates(session: Session = Depends(get_session)):
    return list_all(Mandate, session)


@app.get("/mandates/{mandate_id}", response_model=Mandate, tags=["mandate"])
def get_mandate(mandate_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(Mandate, mandate_id, session, "Mandat introuvable")


@app.post("/mandates", response_model=Mandate, status_code=201, tags=["mandate"])
def create_mandate(mandate: Mandate, session: Session = Depends(get_session)):
    return create_one(mandate, session)


@app.put("/mandates/{mandate_id}", response_model=Mandate, tags=["mandate"])
def update_mandate(mandate_id: int, data: Mandate, session: Session = Depends(get_session)):
    mandate = get_one_or_404(Mandate, mandate_id, session, "Mandat introuvable")
    return replace_one(mandate, data, session)


@app.delete("/mandates/{mandate_id}", response_model=Mandate, tags=["mandate"])
def delete_mandate(mandate_id: int, session: Session = Depends(get_session)):
    mandate = get_one_or_404(Mandate, mandate_id, session, "Mandat introuvable")
    return delete_one(mandate, session)


# ----------------------------------------------------------------------
# ESTATE
# ----------------------------------------------------------------------
@app.get("/estates", response_model=List[Estate], tags=["estate"])
def get_estates(session: Session = Depends(get_session)):
    return list_all(Estate, session)


@app.get("/estates/{estate_id}", response_model=Estate, tags=["estate"])
def get_estate(estate_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(Estate, estate_id, session, "Bien introuvable")


@app.post("/estates", response_model=Estate, status_code=201, tags=["estate"])
def create_estate(estate: Estate, session: Session = Depends(get_session)):
    return create_one(estate, session)


@app.put("/estates/{estate_id}", response_model=Estate, tags=["estate"])
def update_estate(estate_id: int, data: Estate, session: Session = Depends(get_session)):
    estate = get_one_or_404(Estate, estate_id, session, "Bien introuvable")
    return replace_one(estate, data, session)


@app.delete("/estates/{estate_id}", response_model=Estate, tags=["estate"])
def delete_estate(estate_id: int, session: Session = Depends(get_session)):
    estate = get_one_or_404(Estate, estate_id, session, "Bien introuvable")
    return delete_one(estate, session)


# ----------------------------------------------------------------------
# ESTATE_PROPOSED
# ----------------------------------------------------------------------
@app.get("/estate-proposed", response_model=List[EstateProposed], tags=["estate_proposed"])
def get_estate_proposed_list(session: Session = Depends(get_session)):
    return list_all(EstateProposed, session)


@app.get("/estate-proposed/{estate_proposed_id}", response_model=EstateProposed, tags=["estate_proposed"])
def get_estate_proposed(estate_proposed_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(EstateProposed, estate_proposed_id, session, "Proposition de bien introuvable")


@app.post("/estate-proposed", response_model=EstateProposed, status_code=201, tags=["estate_proposed"])
def create_estate_proposed(estate_proposed: EstateProposed, session: Session = Depends(get_session)):
    return create_one(estate_proposed, session)


@app.put("/estate-proposed/{estate_proposed_id}", response_model=EstateProposed, tags=["estate_proposed"])
def update_estate_proposed(estate_proposed_id: int, data: EstateProposed, session: Session = Depends(get_session)):
    estate_proposed = get_one_or_404(EstateProposed, estate_proposed_id, session, "Proposition de bien introuvable")
    return replace_one(estate_proposed, data, session)


@app.delete("/estate-proposed/{estate_proposed_id}", response_model=EstateProposed, tags=["estate_proposed"])
def delete_estate_proposed(estate_proposed_id: int, session: Session = Depends(get_session)):
    estate_proposed = get_one_or_404(EstateProposed, estate_proposed_id, session, "Proposition de bien introuvable")
    return delete_one(estate_proposed, session)


# ----------------------------------------------------------------------
# ESTATE_SEARCHREQUEST
# ----------------------------------------------------------------------
@app.get("/estate-search-requests", response_model=List[EstateSearchRequest], tags=["estate_searchrequest"])
def get_estate_search_requests(session: Session = Depends(get_session)):
    return list_all(EstateSearchRequest, session)


@app.get("/estate-search-requests/{estate_search_request_id}", response_model=EstateSearchRequest, tags=["estate_searchrequest"])
def get_estate_search_request(estate_search_request_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(EstateSearchRequest, estate_search_request_id, session, "Média introuvable")


@app.post("/estate-search-requests", response_model=EstateSearchRequest, status_code=201, tags=["estate_searchrequest"])
def create_estate_search_request(estate_search_request: EstateSearchRequest, session: Session = Depends(get_session)):
    return create_one(estate_search_request, session)


@app.put("/estate-search-requests/{estate_search_request_id}", response_model=EstateSearchRequest, tags=["estate_searchrequest"])
def update_estate_search_request(estate_search_request_id: int, data: EstateSearchRequest, session: Session = Depends(get_session)):
    estate_search_request = get_one_or_404(EstateSearchRequest, estate_search_request_id, session, "Média introuvable")
    return replace_one(estate_search_request, data, session)


@app.delete("/estate-search-requests/{estate_search_request_id}", response_model=EstateSearchRequest, tags=["estate_searchrequest"])
def delete_estate_search_request(estate_search_request_id: int, session: Session = Depends(get_session)):
    estate_search_request = get_one_or_404(EstateSearchRequest, estate_search_request_id, session, "Média introuvable")
    return delete_one(estate_search_request, session)


# ----------------------------------------------------------------------
# PICTURE
# ----------------------------------------------------------------------
@app.get("/pictures", response_model=List[Picture], tags=["picture"])
def get_pictures(session: Session = Depends(get_session)):
    return list_all(Picture, session)


@app.get("/pictures/{picture_id}", response_model=Picture, tags=["picture"])
def get_picture(picture_id: int, session: Session = Depends(get_session)):
    return get_one_or_404(Picture, picture_id, session, "Photo introuvable")


@app.post("/pictures", response_model=Picture, status_code=201, tags=["picture"])
def create_picture(picture: Picture, session: Session = Depends(get_session)):
    return create_one(picture, session)


@app.put("/pictures/{picture_id}", response_model=Picture, tags=["picture"])
def update_picture(picture_id: int, data: Picture, session: Session = Depends(get_session)):
    picture = get_one_or_404(Picture, picture_id, session, "Photo introuvable")
    return replace_one(picture, data, session)


@app.delete("/pictures/{picture_id}", response_model=Picture, tags=["picture"])
def delete_picture(picture_id: int, session: Session = Depends(get_session)):
    picture = get_one_or_404(Picture, picture_id, session, "Photo introuvable")
    return delete_one(picture, session)
