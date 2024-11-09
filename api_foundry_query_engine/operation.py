class Operation:
    def __init__(
        self,
        *,
        entity: str,
        action: str,
        query_params={},
        store_params={},
        metadata_params={},
    ):
        self.entity = entity
        self.action = action
        self.query_params = query_params
        self.store_params = store_params
        self.metadata_params = metadata_params
