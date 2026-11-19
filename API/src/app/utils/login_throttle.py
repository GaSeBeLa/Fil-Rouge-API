"""
login_throttle.py — Frein aux mots de passe essayés en série (POST /auth/login).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Trouvé par Gabriel le 2026-11-09 : 15 mauvais mots de passe d'affilée
passaient tous ; seul argon2 (~430 ms par essai) ralentissait.

Règle : trop d'échecs pour une même clé dans la fenêtre -> la clé est
bloquée un temps, même avec le bon mot de passe ; la route rend alors 429
et l'en-tête `Retry-After`. Deux freins, posés par auth_router :
- par EMAIL (5 échecs en 15 min) : le mot de passe d'un compte précis ;
- par IP (20 échecs en 15 min) : une machine qui essaie beaucoup d'emails.
  Plus large que l'email : toute une salle de classe peut partager une IP.
Une connexion réussie remet à zéro le compte de l'email, pas celui de l'IP.

Les compteurs vivent en mémoire, dans le processus : un redémarrage les
efface, et plusieurs processus uvicorn en tiendraient chacun les leurs.
Assez pour un seul conteneur `api` ; au-delà, il faudrait un stockage
partagé (Redis, par exemple).
============================================================================
"""

import threading
import time
from collections.abc import Callable
from typing import Optional


class LoginThrottle:
    """Compte les échecs récents par clé et bloque la clé au-delà d'un seuil."""

    def __init__(
        self,
        max_failures: int,
        window: float,
        lockout: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """`window` et `lockout` en secondes ; `clock` remplaçable par les tests."""
        self._max_failures = max_failures
        self._window = window
        self._lockout = lockout
        self._clock = clock
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> Optional[int]:
        """
        Secondes à attendre si `key` est bloquée (au moins 1), sinon None.
        Un blocage échu est oublié au passage.
        """
        with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return None
            remaining = until - self._clock()
            if remaining <= 0:
                del self._locked_until[key]
                return None
            return max(1, int(remaining + 0.999))

    def record_failure(self, key: str) -> None:
        """
        Note un échec pour `key`. Au seuil atteint dans la fenêtre, bloque
        `key` pour `lockout` secondes et vide ses échecs. Les échecs plus
        vieux que la fenêtre ne comptent plus.
        """
        with self._lock:
            now = self._clock()
            recent = [t for t in self._failures.get(key, []) if now - t < self._window]
            recent.append(now)
            if len(recent) >= self._max_failures:
                self._locked_until[key] = now + self._lockout
                self._failures.pop(key, None)
            else:
                self._failures[key] = recent

    def reset(self, key: str) -> None:
        """Oublie les échecs et le blocage de `key` ; sans effet sur une clé inconnue."""
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self) -> None:
        """Oublie toutes les clés (utilisé entre deux tests)."""
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()


_FIFTEEN_MINUTES = 15 * 60
_FIVE_MINUTES = 5 * 60

by_email = LoginThrottle(max_failures=5, window=_FIFTEEN_MINUTES, lockout=_FIVE_MINUTES)
by_ip = LoginThrottle(max_failures=20, window=_FIFTEEN_MINUTES, lockout=_FIVE_MINUTES)
