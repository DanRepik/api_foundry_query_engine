import pytest

from api_foundry_query_engine.connectors.postgres_connection import PostgresCursor


class FakeCursor:
    def __init__(self):
        self.description = [
            ("summary_id", None, None, None, None, None, None),
            ("subject_type", None, None, None, None, None, None),
            ("subject_id", None, None, None, None, None, None),
            ("prompt_id", None, None, None, None, None, None),
            ("summary_text", None, None, None, None, None, None),
            ("metadata", None, None, None, None, None, None),
            ("created_at", None, None, None, None, None, None),
            ("updated_at", None, None, None, None, None, None),
        ]
        self.rows = [
            (
                "summary-1",
                "artifact_version",
                "version-1",
                "prompt-1",
                "short summary",
                {"kind": "artifact"},
                "2026-04-29T12:00:00Z",
                "2026-04-29T12:00:01Z",
            )
        ]
        self.executed = None

    def execute(self, sql, params):
        self.executed = (sql, params)

    def __iter__(self):
        return iter(self.rows)

    def close(self):
        return None


@pytest.mark.unit
def test_postgres_cursor_maps_records_by_cursor_description_not_selection_order():
    cursor = FakeCursor()
    wrapped = PostgresCursor(cursor)

    selection_results = {
        "created_at": object(),
        "metadata": object(),
        "prompt_id": object(),
        "subject_id": object(),
        "subject_type": object(),
        "summary_id": object(),
        "summary_text": object(),
        "updated_at": object(),
    }

    result = wrapped.execute("SELECT 1", {"artifact_version_id": "version-1"}, selection_results)

    assert cursor.executed == ("SELECT 1", {"artifact_version_id": "version-1"})
    assert result == [
        {
            "summary_id": "summary-1",
            "subject_type": "artifact_version",
            "subject_id": "version-1",
            "prompt_id": "prompt-1",
            "summary_text": "short summary",
            "metadata": {"kind": "artifact"},
            "created_at": "2026-04-29T12:00:00Z",
            "updated_at": "2026-04-29T12:00:01Z",
        }
    ]
