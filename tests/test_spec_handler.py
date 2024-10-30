import pytest

from api_foundry_query_engine.utils.spec_handler import SpecificationHandler
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)

spec = {
    "components": {
        "schemas": {
            "artist": {
                "type": "object",
                "properties": {
                    "artist_id": {"type": "integer"},
                    "name": {"type": "string", "maxLength": 120},
                    "album_items": {
                        "type": "array",
                        "items": {
                            "$ref": "#/components/schemas/album",
                            "x-af-child-property": "artist_id",
                        },
                    },
                },
            },
            "album": {
                "type": "object",
                "properties": {
                    "album_id": {"type": "integer", "x-af-primary-key": "auto"},
                    "title": {"type": "string", "maxLength": 160},
                    "artist_id": {"type": "integer"},
                },
            },
        }
    }
}


@pytest.mark.unit
class TestSpecHandler:
    def test_traverse_spec_simple(self):
        spec_handler = SpecificationHandler(spec)

        result = spec_handler.traverse_spec(
            spec, ["components", "schemas", "artist", "properties"]
        )
        log.info(f"result: {result}")

        assert result["artist_id"]

    def test_traverse_spec_with_ref(self):
        spec_handler = SpecificationHandler(spec)

        result = spec_handler.traverse_spec(
            spec,
            [
                "components",
                "schemas",
                "artist",
                "properties",
                "album_items",
                "items",
                "properties",
            ],
        )
        log.info(f"result: {result}")

        assert result["album_id"]

    def test_get_simple(self):
        spec_handler = SpecificationHandler(spec)

        artist_schema = spec_handler.traverse_spec(
            spec, ["components", "schemas", "artist"]
        )

        assert artist_schema
        result = spec_handler.get(artist_schema, "properties")
        log.info(f"result: {result}")

        assert result
        assert result["artist_id"]

    def test_get_with_ref(self):
        spec_handler = SpecificationHandler(spec)

        items = spec_handler.traverse_spec(
            spec,
            ["components", "schemas", "artist", "properties", "album_items", "items"],
        )

        log.info(f"items: {items}")
        assert items
        result = spec_handler.get(items, "properties")
        log.info(f"result: {result}")
        assert result
        assert result["album_id"] == {"type": "integer", "x-af-primary-key": "auto"}
