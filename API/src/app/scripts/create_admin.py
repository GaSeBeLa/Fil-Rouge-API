"""
create_admin.py — Crée le premier compte Admin d'une base locale.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le problème : pour avoir un jeton, il faut un compte actif ; pour créer un
compte par l'API (`POST /users`), il faut déjà le jeton d'un Admin. Or la
base de dev n'a aucun compte actif : les comptes repris ont un faux mot de
passe, à refaire. Ce script casse ce cercle, une fois par base locale.

Lancement, depuis `docker/` (le conteneur `api` doit tourner) :

    docker compose exec api python -m src.app.scripts.create_admin

Il demande l'email, puis le mot de passe deux fois, sans l'afficher. Le
compte est créé avec le rôle `Admin`, déjà activé.

Mêmes règles que `POST /users` : l'email est validé par `UserCreate`, le
mot de passe fait 12 caractères au moins et n'est stocké qu'haché (Argon2,
`UserService.create`, ADR-016). Un email déjà pris, aux majuscules près,
est refusé : rien n'est écrit.

Sans terminal (`docker compose exec -T`, ou Git Bash sans `winpty`), le
mot de passe se lit sur l'entrée standard, une ligne, sans confirmation.

Le mot de passe ne s'écrit nulle part ailleurs que dans la base, haché :
ni dans un fichier, ni dans git.
============================================================================
"""

import getpass
import sys

from pydantic import ValidationError
from sqlmodel import Session

from ..conf.database import engine
from ..models import UserCreate
from ..repositories.role_repository import RoleRepository
from ..repositories.user_repository import UserRepository
from ..services.user_service import UserService
from ..utils.exceptions import ConflictError

ADMIN_ROLE = "Admin"


def _read_password() -> str:
    """Le mot de passe, sans l'afficher ; confirmé seulement dans un terminal."""
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Mot de passe (12 caractères au moins) : ")
    if getpass.getpass("Le même, encore une fois : ") != first:
        raise SystemExit("❌ Les deux mots de passe diffèrent : rien n'est créé.")
    return first


def main() -> None:
    """Demande email et mot de passe, puis crée le compte Admin activé."""
    email = input("Email du compte Admin : ").strip()
    password = _read_password()

    with Session(engine) as session:
        role = RoleRepository().get_by_wording(session, ADMIN_ROLE)
        if role is None or role.id is None:
            raise SystemExit("❌ Le rôle 'Admin' manque dans la table role : la base est-elle initialisée ?")
        try:
            item = UserCreate(email=email, password=password, is_activated=True, id_role=role.id)
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc']))} : {e['msg']}" for e in exc.errors())
            raise SystemExit(f"❌ Saisie refusée ({problems}) : rien n'est créé.") from exc

        users = UserRepository()
        if users.find_by_email_ignoring_case(session, item.email) is not None:
            raise SystemExit(f"❌ L'email {item.email} a déjà un compte : rien n'est créé.")
        try:
            user = UserService(users).create(session, item)
        except ConflictError as exc:
            raise SystemExit(f"❌ La base refuse le compte ({exc}) : rien n'est créé.") from exc

    print(f"✅ Compte Admin créé : id {user.id}, {user.email}.")
    print("➡️ Connexion : POST /auth/login dans le Swagger, http://localhost:8000/docs")


if __name__ == "__main__":
    main()
