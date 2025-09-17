import pytest

from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.transactional_service import TransactionalService

log = logger(__name__)


@pytest.mark.integration
class TestCustomOperations:
    def test_top_albums(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="top_selling_albums",
                action="read",
                query_params={
                    "start": "2021-03-01T00:00:00",
                    "end": "2021-04-07T00:00:00",
                },
            )
        )

        log.debug(f"result: {result}")
        log.debug(f"len: {len(result)}")
        assert len(result) == 10

        assert result[0] == {
            "album_id": 55,
            "album_title": "Chronicle, Vol. 2",
            "total_sold": 9,
        }
        assert result[1] == {
            "album_id": 39,
            "album_title": "International Superhits",
            "total_sold": 8,
        }
        assert result[4] == {
            "album_id": 38,
            "album_title": "Heart of the Night",
            "total_sold": 3,
        }

    def test_top_albums_rename(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="top_selling_albums_rename",
                action="read",
                query_params={
                    "start": "2021-03-01T00:00:00",
                    "end": "2021-04-07T00:00:00",
                },
            )
        )

        log.debug(f"result: {result}")
        log.debug(f"len: {len(result)}")
        assert len(result) == 10

        assert result[0] == {
            "album_id": 55,
            "album_title": "Chronicle, Vol. 2",
            "total_sold": 9,
        }
        assert result[1] == {
            "album_id": 39,
            "album_title": "International Superhits",
            "total_sold": 8,
        }
        assert result[4] == {
            "album_id": 38,
            "album_title": "Heart of the Night",
            "total_sold": 3,
        }
