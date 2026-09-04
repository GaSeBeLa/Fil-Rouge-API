"""
services — Couche métier : une classe par table, chacune héritant de
BaseService (voir base_service.py). C'est ici, et seulement ici, que
viendraient des règles comme "hasher le mot de passe avant de créer un
User" ou "un client ne peut pas aussi être hunter" — pas dans les routers
(HTTP) ni dans les repositories (accès aux données).
"""
