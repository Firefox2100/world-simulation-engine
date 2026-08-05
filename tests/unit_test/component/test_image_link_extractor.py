from world_simulation_engine.component.sillytavern_converter.image_link_extractor import ImageLinkExtractor
from world_simulation_engine.model.silly_tavern import (
    SillyTavernCardV3, SillyTavernCardV3Asset, SillyTavernCardV3BookEntry, SillyTavernCardV3Data,
    SillyTavernCardV3LoreBook,
)


def make_card(**data_kwargs) -> SillyTavernCardV3:
    defaults = dict(name="Test")
    defaults.update(data_kwargs)
    return SillyTavernCardV3(spec="chara_card_v3", spec_version="3.0", data=SillyTavernCardV3Data(**defaults))


def test_extracts_url_from_first_message():
    card = make_card(first_mes="Here's my look: http://example.com/a.png yay")

    result = ImageLinkExtractor.extract(card)

    assert [c.url for c in result.candidates] == ["http://example.com/a.png"]
    assert result.candidates[0].source == "first_message"


def test_strips_trailing_sentence_punctuation():
    card = make_card(first_mes="See http://example.com/a.png.")

    result = ImageLinkExtractor.extract(card)

    assert result.candidates[0].url == "http://example.com/a.png"


def test_extracts_url_from_enabled_lorebook_entry_only():
    card = make_card(character_book=SillyTavernCardV3LoreBook(entries=[
        SillyTavernCardV3BookEntry(
            keys=["k"], content="http://example.com/enabled.png", enabled=True,
            insertion_order=0, use_regex=False, constant=False, id=1,
        ),
        SillyTavernCardV3BookEntry(
            keys=["k"], content="http://example.com/disabled.png", enabled=False,
            insertion_order=1, use_regex=False, constant=False, id=2,
        ),
    ]))

    result = ImageLinkExtractor.extract(card)

    assert [c.url for c in result.candidates] == ["http://example.com/enabled.png"]
    assert result.candidates[0].source == "lorebook"
    assert result.candidates[0].source_item_id == "1"


def test_extracts_http_asset_uri_but_skips_non_http_scheme():
    card = make_card(assets=[
        SillyTavernCardV3Asset(type="icon", uri="https://cdn.example.com/icon.png", name="icon", ext="png"),
        SillyTavernCardV3Asset(type="icon", uri="ccdefault:", name="embedded", ext="png"),
    ])

    result = ImageLinkExtractor.extract(card)

    assert [c.url for c in result.candidates] == ["https://cdn.example.com/icon.png"]
    assert result.candidates[0].source == "asset"


def test_extracts_url_from_extensions_script_content():
    card = make_card(extensions={
        "tavern_helper": {"scripts": [
            {"name": "s", "enabled": True, "content": 'const bg = "http://example.com/bg.png";'},
        ]},
    })

    result = ImageLinkExtractor.extract(card)

    assert [c.url for c in result.candidates] == ["http://example.com/bg.png"]
    assert result.candidates[0].source == "script"


def test_dedupes_the_same_url_across_sources_keeping_first_occurrence():
    card = make_card(
        first_mes="http://example.com/shared.png",
        character_book=SillyTavernCardV3LoreBook(entries=[
            SillyTavernCardV3BookEntry(
                keys=["k"], content="http://example.com/shared.png", enabled=True,
                insertion_order=0, use_regex=False, constant=False,
            ),
        ]),
    )

    result = ImageLinkExtractor.extract(card)

    assert len(result.candidates) == 1
    assert result.candidates[0].source == "first_message"


def test_catch_all_pass_finds_urls_in_fields_no_labelled_scan_covers():
    card = make_card(
        description="See http://example.com/description.png for my look.",
        personality="", scenario="", creator_notes="http://example.com/notes.png",
    )

    result = ImageLinkExtractor.extract(card)

    urls = {c.url: c.source for c in result.candidates}
    assert urls == {
        "http://example.com/description.png": "other",
        "http://example.com/notes.png": "other",
    }


def test_catch_all_pass_still_skips_disabled_lorebook_entries():
    card = make_card(character_book=SillyTavernCardV3LoreBook(entries=[
        SillyTavernCardV3BookEntry(
            keys=["k"], content="http://example.com/disabled.png", enabled=False,
            insertion_order=0, use_regex=False, constant=False, id=1,
        ),
    ]))

    result = ImageLinkExtractor.extract(card)

    assert result.candidates == []


def test_catch_all_pass_does_not_duplicate_a_url_a_labelled_scan_already_found():
    card = make_card(first_mes="http://example.com/shared.png")

    result = ImageLinkExtractor.extract(card)

    assert len(result.candidates) == 1
    assert result.candidates[0].source == "first_message"


def test_no_candidates_when_nothing_looks_like_a_url():
    card = make_card(first_mes="No links here at all.")

    result = ImageLinkExtractor.extract(card)

    assert result.candidates == []
