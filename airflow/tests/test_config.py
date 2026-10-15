"""Tests de airflow/src/config.py : chaque réglage vient de la bonne variable."""
from __future__ import annotations

import pytest

from src.config import Buckets, DatabaseConfig, MinIOConfig, MissingSettingError


def test_minio_reads_its_variables(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "http://example:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")

    cfg = MinIOConfig.from_env()

    assert (cfg.endpoint, cfg.access_key, cfg.secret_key) == ("http://example:9000", "ak", "sk")


def test_minio_endpoint_defaults_to_compose_service(monkeypatch):
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)

    assert MinIOConfig.from_env().endpoint == "http://minio:9000"


@pytest.mark.parametrize("name", ["MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"])
def test_minio_secret_has_no_default(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)

    with pytest.raises(MissingSettingError, match=name):
        MinIOConfig.from_env()


def test_buckets_default_to_the_four_decided(monkeypatch):
    for name in ("BUCKET_BRONZE", "BUCKET_SILVER", "BUCKET_GOLD", "BUCKET_QUARANTINE"):
        monkeypatch.delenv(name, raising=False)

    assert Buckets.from_env() == Buckets("bronze", "silver", "gold", "quarantine")


def test_buckets_read_their_variables(monkeypatch):
    monkeypatch.setenv("BUCKET_BRONZE", "b")
    monkeypatch.setenv("BUCKET_SILVER", "s")
    monkeypatch.setenv("BUCKET_GOLD", "g")
    monkeypatch.setenv("BUCKET_QUARANTINE", "q")

    assert Buckets.from_env() == Buckets("b", "s", "g", "q")


def test_database_reads_its_variables(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "dbhost")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "base")
    monkeypatch.setenv("POSTGRES_USER", "moi")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    assert DatabaseConfig.from_env() == DatabaseConfig("dbhost", 6543, "base", "moi", "secret")


@pytest.mark.parametrize("name", ["POSTGRES_USER", "POSTGRES_PASSWORD"])
def test_database_secret_has_no_default(monkeypatch, name):
    monkeypatch.setenv(name, "")

    with pytest.raises(MissingSettingError, match=name):
        DatabaseConfig.from_env()


def test_database_url_encodes_the_password():
    cfg = DatabaseConfig("db", 5432, "fil_rouge_immobilier", "postgres", "a@b/c:d")

    assert cfg.url() == "postgresql+psycopg2://postgres:a%40b%2Fc%3Ad@db:5432/fil_rouge_immobilier"
