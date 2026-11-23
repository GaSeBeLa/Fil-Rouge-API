"""
repositories — Couche d'accès aux données : une classe par table, chacune
héritant de BaseRepository (voir base_repository.py). Presque seule cette
couche touche directement à la Session SQLModel/SQLAlchemy. Exceptions :
services/activation_service.py, services/suggestion_service.py, les
services/*_rows.py, et utils/current_user.py et utils/roles.py (la fiche
du compte connecté).
"""
