"""
print_rights_matrix.py — La matrice des droits, relevée dans l'API elle-même.

Pour chaque route, lit les rôles admis par `require_roles` (utils/roles.py)
dans les dépendances FastAPI, et imprime un tableau Markdown : une ligne par
table, une colonne par geste (lire, créer, modifier), puis les routes à part.
Ce que vérifient les services en plus (l'auteur d'une note…) n'y est pas :
ce n'est pas une dépendance.

À lancer dans le conteneur `api`, qui a le code et ses paquets, depuis
docker/ :
    bash :       docker compose exec -T api python - < tools/print_rights_matrix.py
    PowerShell : Get-Content tools/print_rights_matrix.py | docker compose exec -T api python -
"""

from collections import defaultdict

from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import get_parameterless_sub_dependant
from fastapi.routing import APIRoute

import src.app.main as main
from src.app.utils.roles import ALL_ROLES, WRITER_ROLES

CRUD_ACTIONS = {("GET", False): "Lire", ("GET", True): "Lire", ("POST", False): "Créer", ("PUT", True): "Modifier"}


def walk(dependant: Dependant, allowed: list[set[str]], seen: set[str]) -> None:
    call = dependant.call
    name = getattr(call, "__name__", "")
    seen.add(name)
    if name == "_check" and call is not None and call.__closure__:
        for cell in call.__closure__:
            if isinstance(cell.cell_contents, tuple):
                allowed.append(set(cell.cell_contents))
    for sub in dependant.dependencies:
        walk(sub, allowed, seen)


def who(route: APIRoute, router_dependencies: list) -> str:
    allowed: list[set[str]] = []
    seen: set[str] = set()
    walk(route.dependant, allowed, seen)
    for dependency in router_dependencies:
        walk(get_parameterless_sub_dependant(depends=dependency, path=route.path_format), allowed, seen)
    if "get_current_user" not in seen:
        return "clé d'API seule" if "require_api_key" in seen else "ouvert"
    roles = set(ALL_ROLES)
    for group in allowed:
        roles &= group
    if roles == set(ALL_ROLES):
        return "tous"
    if roles == set(WRITER_ROLES):
        return "tous sauf Reader"
    return ", ".join(role for role in ALL_ROLES if role in roles) or "personne"


def api_routes():
    # FastAPI 0.143 garde chaque include_router comme un bloc (_IncludedRouter) :
    # ses routes sont dans le routeur d'origine.
    for entry in main.app.routes:
        router = getattr(entry, "router", None) or getattr(entry, "original_router", None)
        if router is not None and getattr(router, "routes", None) is not None:
            for route in router.routes:
                if isinstance(route, APIRoute):
                    yield route, list(router.dependencies)
        elif isinstance(entry, APIRoute):
            yield entry, []


def main_() -> None:
    crud: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    others: list[tuple[str, str, str]] = []
    count = 0
    for route, router_dependencies in api_routes():
        for method in sorted(route.methods or ()):
            count += 1
            parts = route.path.strip("/").split("/")
            prefix = "/" + parts[0]
            is_crud_path = route.path != "/" and (len(parts) == 1 or parts[1:] == ["{item_id}"])
            action = CRUD_ACTIONS.get((method, len(parts) == 2))
            if action and is_crud_path:
                crud[prefix][action].add(who(route, router_dependencies))
            else:
                others.append((method, route.path, who(route, router_dependencies)))

    print("| Table (route) | Lire | Créer | Modifier |")
    print("|---|---|---|---|")
    for prefix, actions in crud.items():
        cells = [" / ".join(sorted(actions.get(a, {"—"}))) for a in ("Lire", "Créer", "Modifier")]
        print(f"| `{prefix}` | " + " | ".join(cells) + " |")
    print()
    print("| Route à part | Qui |")
    print("|---|---|")
    for method, path, roles in others:
        print(f"| `{method} {path}` | {roles} |")
    print()
    print(f"{count} opérations relevées.")


main_()
