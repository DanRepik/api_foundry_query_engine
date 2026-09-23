import pytest

from api_foundry_query_engine.connectors.connection import parse_engine


@pytest.mark.unit
class TestParseEngine:
    def test_bare_dialect_resolves_default_driver(self):
        assert parse_engine("postgres") == ("postgres", "psycopg2")

    def test_explicit_driver_is_used_verbatim(self):
        assert parse_engine("postgres:data-api") == ("postgres", "data-api")

    def test_explicit_driver_overrides_any_default(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_DEFAULT_DRIVER", "data-api")
        assert parse_engine("postgres:psycopg2") == ("postgres", "psycopg2")

    def test_env_var_overrides_bare_dialect_default(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_DEFAULT_DRIVER", "data-api")
        assert parse_engine("postgres") == ("postgres", "data-api")

    def test_oracle_and_mysql_have_named_defaults_for_sql_generation(self):
        # No real connector is registered for either (see
        # ConnectionFactory.CONNECTOR_REGISTRY) -- only SQLQueryHandler's
        # dialect-specific SQL generation uses these today -- but a bare
        # "oracle"/"mysql" engine value must still resolve, not raise.
        assert parse_engine("oracle") == ("oracle", "cx_oracle")
        assert parse_engine("mysql") == ("mysql", "mysqlclient")

    def test_bare_dialect_with_no_default_and_no_env_var_raises(self):
        with pytest.raises(ValueError, match="No default driver configured for dialect 'mssql'"):
            parse_engine("mssql")

    def test_dialect_with_no_default_but_env_var_set_is_resolved(self, monkeypatch):
        monkeypatch.setenv("MSSQL_DEFAULT_DRIVER", "pytds")
        assert parse_engine("mssql") == ("mssql", "pytds")
