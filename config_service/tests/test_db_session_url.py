import pytest
from src.db.session import get_database_url


def test_get_database_url_prefers_database_url_when_set(monkeypatch):
    monkeypatch.setenv("DOTENV_AUTOLOAD", "0")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg2://u:p@host:5432/db?sslmode=require"
    )
    monkeypatch.delenv("DATABASE_URL_TUNNEL", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    assert get_database_url().startswith("postgresql+psycopg2://u:p@host:5432/db")


def test_get_database_url_assembles_from_components(monkeypatch):
    monkeypatch.setenv("DOTENV_AUTOLOAD", "0")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_TUNNEL", raising=False)

    monkeypatch.setenv("DB_HOST", "rds.internal")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "opensre_config")
    monkeypatch.setenv("DB_USERNAME", "opensre")
    monkeypatch.setenv("DB_PASSWORD", "p@ss word/with:chars")
    monkeypatch.setenv("DB_SSLMODE", "require")

    url = get_database_url()
    assert url.startswith("postgresql+psycopg2://opensre:")
    assert "@rds.internal:5432/opensre_config?sslmode=require" in url
    # ensure url-encoding happened (space => + or %20)
    assert ("p%40ss+word%2Fwith%3Achars" in url) or (
        "p%40ss%20word%2Fwith%3Achars" in url
    )


def test_get_database_url_raises_if_nothing_set(monkeypatch):
    monkeypatch.setenv("DOTENV_AUTOLOAD", "0")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_TUNNEL", raising=False)
    for k in (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USERNAME",
        "DB_PASSWORD",
        "DB_SSLMODE",
    ):
        monkeypatch.delenv(k, raising=False)

    with pytest.raises(RuntimeError):
        get_database_url()
