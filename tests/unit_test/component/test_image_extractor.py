import base64
from unittest.mock import AsyncMock

from world_simulation_engine.component.sillytavern_converter import ImageExtractor
from world_simulation_engine.model.silly_tavern import SillyTavernCardV3, SillyTavernCardV3Data
from world_simulation_engine.service.media_download_service import DownloadedImage, ImageProbeResult
from world_simulation_engine.service.storage_service import StagedObject, StoredObject


def make_card(first_mes: str) -> SillyTavernCardV3:
    return SillyTavernCardV3(
        spec="chara_card_v3", spec_version="3.0", data=SillyTavernCardV3Data(name="Test", first_mes=first_mes),
    )


def make_card_with_script(url: str) -> SillyTavernCardV3:
    return SillyTavernCardV3(
        spec="chara_card_v3", spec_version="3.0",
        data=SillyTavernCardV3Data(
            name="Test", first_mes="",
            extensions={"regex_scripts": [{}, {}, {}, {"replaceString": f'<img src="{url}">'}]},
        ),
    )


def make_media_download_service(*, safe_urls=None, probe_results=None, downloaded=None):
    service = AsyncMock()
    service.is_safe_url = AsyncMock(side_effect=lambda url: url in (safe_urls or set()))
    service.probe_many = AsyncMock(return_value=probe_results or [])
    service.download_many = AsyncMock(return_value=[(item.url, item.content) for item in (downloaded or [])])
    return service


def make_storage():
    storage = AsyncMock()
    storage.stage_bytes = AsyncMock(
        return_value=StagedObject(token="1" * 32, digest="a" * 64, size=3),
    )
    return storage


def make_downloaded(url: str) -> DownloadedImage:
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    return DownloadedImage(url=url, stored=StoredObject(digest="a" * 64, size=len(png)), content=png)


async def test_extract_returns_empty_when_no_urls_found():
    card = make_card("nothing to see here")
    extractor = ImageExtractor(
        media_download_service=make_media_download_service(), storage=make_storage(), whitelist=[],
    )

    result = await extractor.extract(card)

    assert result.media_rows == []
    assert result.candidates == []
    assert result.summary.found == 0


async def test_summary_counts_reflect_every_outcome():
    whitelisted_url = "https://trusted.example.com/a.png"
    review_url = "https://other.example.com/b.png"
    unsafe_url = "http://internal.example.com/c.png"
    non_image_url = "https://other.example.com/d.html"
    card = make_card(f"{whitelisted_url} {review_url} {unsafe_url} {non_image_url}")
    media_download_service = make_media_download_service(
        safe_urls={whitelisted_url, review_url, non_image_url},
        downloaded=[make_downloaded(whitelisted_url)],
        probe_results=[
            ImageProbeResult(url=review_url, probably_image=True),
            ImageProbeResult(url=non_image_url, probably_image=False),
        ],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(),
        whitelist=["https://trusted.example.com/"],
    )

    result = await extractor.extract(card)

    assert result.summary.found == 4
    assert result.summary.auto_downloaded == 1
    assert result.summary.awaiting_review == 1
    assert result.summary.dropped_unsafe == 1
    assert result.summary.dropped_non_image == 1
    assert result.summary.failed_downloads == 0


async def test_whitelisted_url_is_downloaded_and_not_shown_as_a_candidate():
    url = "https://trusted.example.com/a.png"
    card = make_card(f"See {url}")
    media_download_service = make_media_download_service(
        safe_urls={url}, downloaded=[make_downloaded(url)],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(),
        whitelist=["https://trusted.example.com/"],
    )

    result = await extractor.extract(card)

    assert len(result.media_rows) == 1
    assert result.media_rows[0]["source_url"] == url
    assert result.candidates == []
    media_download_service.probe_many.assert_awaited_once_with([])


async def test_non_whitelisted_safe_url_is_probed_and_shown_when_probably_an_image():
    url = "https://other.example.com/a.png"
    card = make_card(f"See {url}")
    media_download_service = make_media_download_service(
        safe_urls={url}, probe_results=[ImageProbeResult(url=url, probably_image=True)],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(), whitelist=[],
    )

    result = await extractor.extract(card)

    assert result.media_rows == []
    assert len(result.candidates) == 1
    assert result.candidates[0].url == url
    assert result.candidates[0].probably_image is True


async def test_selected_review_url_is_staged_and_returned_for_preview():
    url = "https://other.example.com/a.png"
    card = make_card(url)
    media_download_service = make_media_download_service(
        safe_urls={url}, downloaded=[make_downloaded(url)],
        probe_results=[ImageProbeResult(url=url, probably_image=True)],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(), whitelist=[],
    )

    result = await extractor.extract(card, selected_urls=[url])

    assert result.candidates == []
    assert result.media_rows[0]["temporary_id"] == "1" * 32
    assert result.media_rows[0]["preview_data_uri"].startswith("data:image/webp;base64,")


async def test_scan_finds_nested_regex_script_url_before_downloading():
    url = "https://origin.picgo.net/2026/05/23/image.png"
    card = make_card_with_script(url)
    media_download_service = make_media_download_service(
        safe_urls={url}, probe_results=[ImageProbeResult(url=url, probably_image=True)],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(), whitelist=[],
    )

    result = await extractor.scan(card)

    assert [candidate.url for candidate in result.candidates] == [url]
    assert result.candidates[0].source == "script"
    assert result.summary.found == 1
    media_download_service.download_many.assert_not_awaited()


async def test_non_whitelisted_url_is_shown_when_head_probe_is_unknown():
    url = "https://other.example.com/a.png"
    card = make_card(f"See {url}")
    media_download_service = make_media_download_service(
        safe_urls={url}, probe_results=[ImageProbeResult(url=url, probably_image=None)],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(), whitelist=[],
    )

    result = await extractor.extract(card)

    assert len(result.candidates) == 1
    assert result.candidates[0].probably_image is None


async def test_non_whitelisted_url_confirmed_non_image_is_dropped_entirely():
    url = "https://other.example.com/a.html"
    card = make_card(f"See {url}")
    media_download_service = make_media_download_service(
        safe_urls={url}, probe_results=[ImageProbeResult(url=url, probably_image=False)],
    )
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(), whitelist=[],
    )

    result = await extractor.extract(card)

    assert result.candidates == []


async def test_unsafe_url_is_dropped_before_whitelist_or_probe():
    url = "http://internal.example.com/a.png"
    card = make_card(f"See {url}")
    media_download_service = make_media_download_service(safe_urls=set())
    extractor = ImageExtractor(
        media_download_service=media_download_service, storage=make_storage(),
        whitelist=["http://internal.example.com/"],  # whitelisting never bypasses the SSRF filter
    )

    result = await extractor.extract(card)

    assert result.media_rows == []
    assert result.candidates == []
    media_download_service.download_many.assert_awaited_once_with([])
