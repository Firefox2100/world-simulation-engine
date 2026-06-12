from pathlib import Path
import aiofiles


class MediaRepository:
    def __init__(self,
                 base_path: Path,
                 ):
        self._base_path = Path(base_path)

    async def get(self, file_name: str) -> bytes:
        async with aiofiles.open(self._base_path / file_name, "rb") as file:
            return await file.read()

    async def save(self, file_name: str, data: bytes) -> None:
        async with aiofiles.open(self._base_path / file_name, "wb") as file:
            await file.write(data)


class SessionStorage:
    def __init__(self,
                 base_path: Path,
                 ):
        self._base_path = Path(base_path)

    @property
    def image(self) -> MediaRepository:
        return MediaRepository(self._base_path / "image")


class StorageService:
    def __init__(self,
                 base_path: str = "data/storage",
                 ):
        self._base_path = Path(base_path)

    def world(self, world_id: int) -> SessionStorage:
        return SessionStorage(self._base_path / "world" / str(world_id))

    def simulation(self, simulation_id: int) -> SessionStorage:
        return SessionStorage(self._base_path / "simulation" / str(simulation_id))

    def temporary(self):
        return SessionStorage(self._base_path / "tmp")
