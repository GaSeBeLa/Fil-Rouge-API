"""
Fixtures partagées des tests de airflow/src/ (chantier FLX).

Ces tests tournent SANS Airflow, SANS Docker et SANS MinIO (cours Airflow,
exo 8 ; modèle : lab/tests/conftest.py). Depuis la racine du dépôt :
    pytest airflow/tests -q
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Rendre airflow/ importable, pour écrire `from src.config import ...` comme
# les DAG ; airflow/src/ aussi, pour l'import « à plat » du lab.
AIRFLOW_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIRFLOW_DIR / "src"))
sys.path.insert(0, str(AIRFLOW_DIR))

# Valeurs factices : config.py exige ces variables (aucun secret par défaut).
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret")
os.environ.setdefault("POSTGRES_USER", "test-user")
os.environ.setdefault("POSTGRES_PASSWORD", "test-password")
