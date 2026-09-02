import abc


class BaseClient(abc.ABC):
    default_name: str

    def has_default_list(self) -> bool:
        return False

    def default_list_name(self) -> str:
        return self.default_name

    @abc.abstractmethod
    def get_list(self, name: str | None = None, **kwargs) -> list:
        pass

    @abc.abstractmethod
    def download(self, *args, **kwargs) -> None:
        pass
