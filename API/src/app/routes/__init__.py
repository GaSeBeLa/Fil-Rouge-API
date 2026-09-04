"""
routers — Couche HTTP : une APIRouter par table, construite par
build_crud_router (voir crud_router.py). C'est la seule couche qui connaît
FastAPI/HTTPException — repositories et services restent indépendants du
framework web.
"""
