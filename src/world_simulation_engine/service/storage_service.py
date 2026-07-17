import asyncio
import hashlib
import os
import re
import io
import uuid
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final
import aiofiles
import aiofiles.os
from PIL import Image, UnidentifiedImageError


_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class StoredObject:
    digest: str
    size: int


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


class StorageService:
    def __init__(self,
                 base_path: str | Path = "data/storage",
                 *,
                 chunk_size: int = 1024 * 1024,
                 max_object_size: int | None = None,
                 durable_writes: bool = False,
                 ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")

        if max_object_size is not None and max_object_size <= 0:
            raise ValueError("max_object_size must be greater than zero")

        self._base_path = Path(base_path)
        self._object_root = self._base_path / "sha256"
        self._temporary_root = self._base_path / ".tmp"

        self._chunk_size = chunk_size
        self._max_object_size = max_object_size
        self._durable_writes = durable_writes

    @staticmethod
    def _normalise_digest(digest: str) -> str:
        normalised = digest.strip().lower()

        if not _SHA256_RE.fullmatch(normalised):
            raise ValueError(
                "SHA-256 digest must contain exactly 64 hexadecimal characters"
            )

        return normalised

    @staticmethod
    async def _unlink_if_exists(path: Path) -> None:
        try:
            await aiofiles.os.unlink(path)
        except FileNotFoundError:
            pass

    @staticmethod
    async def _fsync_directory(path: Path) -> None:
        def sync() -> None:
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

        await asyncio.to_thread(sync)

    @staticmethod
    async def _publish(temporary_path: Path,
                       destination: Path,
                       ) -> None:
        try:
            await asyncio.to_thread(
                os.link,
                temporary_path,
                destination,
            )
        except FileExistsError:
            # Identical content has already been stored, possibly by another
            # process or worker. Since the destination name is the digest,
            # retaining the existing object is correct.
            return

    def _path_for_digest(self, digest: str) -> Path:
        normalised = self._normalise_digest(digest)

        return (
            self._object_root
            / normalised[0:2]
            / normalised[2:4]
            / normalised
        )

    async def initialise(self) -> None:
        await aiofiles.os.makedirs(self._object_root, exist_ok=True)
        await aiofiles.os.makedirs(self._temporary_root, exist_ok=True)

    async def save(self,
                   content: AsyncIterable[bytes],
                   *,
                   expected_digest: str | None = None,
                   ) -> StoredObject:
        if expected_digest is not None:
            expected_digest = self._normalise_digest(expected_digest)

        temporary_path = self._temporary_root / f"{uuid.uuid4().hex}.part"
        digest = hashlib.sha256()
        total_size = 0

        try:
            async with aiofiles.open(temporary_path, mode="xb") as output:
                async for chunk in content:
                    if not isinstance(chunk, bytes):
                        raise TypeError(
                            "content must yield bytes; "
                            f"received {type(chunk).__name__}"
                        )

                    if not chunk:
                        continue

                    total_size += len(chunk)

                    if (
                        self._max_object_size is not None
                        and total_size > self._max_object_size
                    ):
                        raise ValueError(
                            f"Object exceeds maximum size of {self._max_object_size} bytes"
                        )

                    digest.update(chunk)
                    await output.write(chunk)

                await output.flush()

                if self._durable_writes:
                    await asyncio.to_thread(os.fsync, output.fileno())

            actual_digest = digest.hexdigest()

            if (
                expected_digest is not None
                and actual_digest != expected_digest
            ):
                raise ValueError(
                    "Content digest does not match expected digest: "
                    f"expected={expected_digest}, actual={actual_digest}"
                )

            destination = self._path_for_digest(actual_digest)
            await aiofiles.os.makedirs(destination.parent, exist_ok=True)

            await self._publish(temporary_path, destination)

            if self._durable_writes:
                await self._fsync_directory(destination.parent)

            return StoredObject(
                digest=actual_digest,
                size=total_size,
            )

        finally:
            await self._unlink_if_exists(temporary_path)

    async def save_bytes(self,
                         content: bytes,
                         *,
                         expected_digest: str | None = None,
                         ) -> StoredObject:
        async def chunks() -> AsyncIterator[bytes]:
            for offset in range(0, len(content), self._chunk_size):
                yield content[offset : offset + self._chunk_size]

        return await self.save(
            chunks(),
            expected_digest=expected_digest,
        )

    async def get(self,
                  digest: str,
                  *,
                  chunk_size: int | None = None,
                  ) -> AsyncIterator[bytes]:
        path = self._path_for_digest(digest)
        read_size = chunk_size or self._chunk_size

        if read_size <= 0:
            raise ValueError("chunk_size must be greater than zero")

        try:
            async with aiofiles.open(path, mode="rb") as source:
                while chunk := await source.read(read_size):
                    yield chunk
        except FileNotFoundError as exc:
            raise ValueError(f"Object with digest {digest} not found") from exc

    async def get_bytes(self,
                        digest: str,
                        *,
                        max_size: int | None = None,
                        ) -> bytes:
        chunks: list[bytes] = []
        total_size = 0

        async for chunk in self.get(digest):
            total_size += len(chunk)

            if max_size is not None and total_size > max_size:
                raise ValueError(f"Object exceeds in-memory limit of {max_size} bytes")

            chunks.append(chunk)

        return b"".join(chunks)

    async def exists(self, digest: str) -> bool:
        path = self._path_for_digest(digest)
        return await aiofiles.os.path.isfile(path)

    async def stat(self, digest: str) -> StoredObject:
        path = self._path_for_digest(digest)

        try:
            result = await aiofiles.os.stat(path)
        except FileNotFoundError as exc:
            raise ValueError(f"Object with digest {digest} not found") from exc

        return StoredObject(
            digest=self._normalise_digest(digest),
            size=result.st_size,
        )

    async def verify(self, digest: str) -> bool:
        expected_digest = self._normalise_digest(digest)
        actual = hashlib.sha256()

        async for chunk in self.get(expected_digest):
            actual.update(chunk)

        return actual.hexdigest() == expected_digest

    async def delete(self, digest: str, *, missing_ok: bool = False) -> None:
        path = self._path_for_digest(digest)

        try:
            await aiofiles.os.unlink(path)
        except FileNotFoundError:
            if not missing_ok:
                raise ValueError(f"Object with digest {digest} not found")

    def path_for(self, digest: str) -> Path:
        return self._path_for_digest(digest)
