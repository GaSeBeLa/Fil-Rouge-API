"""config.py — Réglages des flux de données, lus dans l'environnement.

Sur le modèle de `airflow/src/config.py` du lab du cours Airflow (dataclass +
`from_env()`), avec une différence : **aucune valeur secrète par défaut**. Un
identifiant ou un mot de passe absent lève une erreur claire au lieu de
tomber en silence sur « minioadmin ».

D'où viennent les valeurs : `docker/docker-compose.yml` les passe aux trois
services Airflow, depuis `docker/.env` (chantier FLX, fiche FLX2).

Deux façons d'atteindre MinIO et la base coexistent, comme dans le lab :
  - ce module, pour le code de `src/` (Python pur, testable sans Airflow) ;
  - les connexions Airflow `minio_default` et `fil_rouge_db` (variables
    `AIRFLOW_CONN_*`), pour les hooks des DAG. Leurs noms sont ici.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

# Noms des connexions Airflow déclarées par AIRFLOW_CONN_MINIO_DEFAULT et
# AIRFLOW_CONN_FIL_ROUGE_DB dans docker-compose.yml.
MINIO_CONN_ID = "minio_default"
FIL_ROUGE_DB_CONN_ID = "fil_rouge_db"


class MissingSettingError(RuntimeError):
    """Une variable d'environnement obligatoire manque ou est vide."""


def _required(name: str) -> str:
    """Lit une variable obligatoire ; absente ou vide, lève MissingSettingError."""
    value = os.getenv(name, "")
    if not value:
        raise MissingSettingError(f"variable d'environnement manquante : {name} (voir docker/.env.exemple)")
    return value


@dataclass(frozen=True)
class MinIOConfig:
    """Connexion à MinIO (S3-compatible)."""

    endpoint: str
    access_key: str
    secret_key: str

    @classmethod
    def from_env(cls) -> MinIOConfig:
        # L'adresse n'est pas un secret : par défaut, le service minio du compose.
        return cls(
            endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            access_key=_required("MINIO_ACCESS_KEY"),
            secret_key=_required("MINIO_SECRET_KEY"),
        )


@dataclass(frozen=True)
class Buckets:
    """Les quatre buckets du lac (décision de Seb, flux-11, 2026-10-15).

    bronze, silver et gold sont les raw, cleansed et curated du cours ;
    quarantine reçoit les lignes rejetées.
    """

    bronze: str
    silver: str
    gold: str
    quarantine: str

    @classmethod
    def from_env(cls) -> Buckets:
        return cls(
            bronze=os.getenv("BUCKET_BRONZE", "bronze"),
            silver=os.getenv("BUCKET_SILVER", "silver"),
            gold=os.getenv("BUCKET_GOLD", "gold"),
            quarantine=os.getenv("BUCKET_QUARANTINE", "quarantine"),
        )


@dataclass(frozen=True)
class DatabaseConfig:
    """Connexion à la base métier fil_rouge_immobilier (service db)."""

    host: str
    port: int
    name: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        # Mêmes noms de variables que le service api (docker-compose.yml).
        return cls(
            host=os.getenv("POSTGRES_HOST", "db"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            name=os.getenv("POSTGRES_DB", "fil_rouge_immobilier"),
            user=_required("POSTGRES_USER"),
            password=_required("POSTGRES_PASSWORD"),
        )

    def url(self) -> str:
        """URL SQLAlchemy de la base.

        Utilisateur et mot de passe encodés, comme dans l'API
        (`API/src/app/conf/database.py`) : un `@` ou un `/` dans le mot de
        passe casserait une URL assemblée à la main.
        """
        return (
            f"postgresql+psycopg2://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.name}"
        )
