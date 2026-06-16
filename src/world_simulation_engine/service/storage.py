import asyncio
import io
import shutil
from pathlib import Path
import aiofiles
from PIL import Image, UnidentifiedImageError


class FormatNormaliser:
    @staticmethod
    def normalise_image(image_data: bytes) -> bytes:
        try:
            image = Image.open(io.BytesIO(image_data))
            image.verify()

            image = Image.open(io.BytesIO(image_data))
        except UnidentifiedImageError:
            raise ValueError("File is not a valid image")

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")

        return png_buffer.getvalue()


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

    def get_path(self, file_name: str) -> Path:
        return self._base_path / file_name


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

    async def copy_world_to_simulation(self,
                                       world_id: int,
                                       simulation_id: int,
                                       overwrite: bool = False,
                                       ):
        src = self._base_path / "world" / str(world_id)
        dst = self._base_path / "simulation" / str(simulation_id)

        if not src.exists():
            return

        if overwrite and dst.exists():
            await asyncio.to_thread(shutil.rmtree, dst)

        await asyncio.to_thread(
            shutil.copytree,
            src,
            dst,
            dirs_exist_ok=overwrite,
        )
