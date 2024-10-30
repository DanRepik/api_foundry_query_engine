class Operation:
    def __init__(
        self,
        *,
        path: str,
        action: str,
        query_params={},
        store_params={},
        metadata_params={},
    ):
        self.path = path
        self.action = action
        self.query_params = query_params
        self.store_params = store_params
        self.metadata_params = metadata_params
