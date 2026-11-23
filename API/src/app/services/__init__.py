"""
services — Couche métier : une classe par table, chacune héritant de
BaseService (voir base_service.py). C'est ici que vivent les règles
métier, comme "hasher le mot de passe avant de créer un User"
(UserService.create) — pas dans routes/ (HTTP) ni dans les repositories
(accès aux données). "Une fiche par compte" est tenue par la base
(trigger check_one_profile_per_user).
"""
