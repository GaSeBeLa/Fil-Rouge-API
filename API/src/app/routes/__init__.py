"""
routes — Couche HTTP : une APIRouter par table, construite par
build_crud_router (voir crud_router.py), et quatre routeurs à part, écrits
à la main (auth, signup, suggestion, recherche de biens :
estate_search_router.py). C'est la seule couche qui connaît
FastAPI/HTTPException — repositories et services restent indépendants du
framework web.
"""
