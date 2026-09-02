class BaseClient:
    def has_default_list(self) -> bool:
        return False

    def get_list(self, name: str | None = None, **kwargs) -> list:
        raise NotImplementedError
