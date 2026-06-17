from abc import ABC, abstractmethod
from httpx import AsyncClient


class ImageBackend(ABC):
    def __init__(self,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 client: AsyncClient | None = None,
                 ):
        self._base_url = base_url
        self._api_key = api_key

        self._client = client or AsyncClient()

    @abstractmethod
    async def generate_image(self,
                             positive_prompt: str,
                             negative_prompt: str,
                             ):
        pass


class ComfyUiBackend(ImageBackend):
    def __init__(self,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 client: AsyncClient | None = None,
                 *,
                 workflow_json: str | None = None,
                 ):
        super().__init__(
            base_url=base_url or "http://localhost",
            api_key=api_key,
            client=client,
        )

        self._workflow_json = workflow_json

    async def generate_image(self,
                             positive_prompt: str,
                             negative_prompt: str,
                             ):
        pass
