"""Deterministic, no-LLM scan for image links embedded in a SillyTavern card. Purely structural
text scanning, so this takes the *raw* `SillyTavernCardV3`, not `PreprocessedCard` -
`CardPreprocessor` already discards `extensions`/`assets` (out of scope for every other stage) and
macro-normalizes free text, neither of which matters for finding a URL substring.

Image links have turned up in real cards in places well beyond the "obvious" three (opening
message, lorebook entry content, V3 `assets`): notably a card whose gallery images lived inside
`extensions.regex_scripts[].replaceString` - a big blob of injected HTML/JS, itself one value
buried inside `extensions`, not a field with any special handling of its own. Rather than
enumerate every free-text field a card spec might ever contain (and inevitably miss the next
one), this does two passes: a handful of *labelled* scans over the fields most commonly used for
image links (better `source` tagging for the review UI), then a catch-all pass over the entire
serialized card (`source="other"`) that catches everything else - description, personality,
scenario, creator notes, system prompt, post-history instructions, example dialogue, alternate
greetings, character_book name/description, per-entry name/comment/extensions, and any
card-spec field this doesn't already know about by name. The `add()` helper dedupes by URL, so
the catch-all pass never double-reports something a labelled scan already found.

No SSRF/safety decisions happen here - this only finds candidate URLs; `ImageExtractor` decides
what's safe to touch and what to do with each one.
"""

import json
import re

from pydantic import BaseModel, Field

from world_simulation_engine.model.silly_tavern import SillyTavernCardV3

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>\]\)\\]+")
_TRAILING_PUNCTUATION = ".,;:!?"


class ImageUrlCandidate(BaseModel):
    url: str
    source: str = Field(
        description="Where this URL was found: 'first_message', 'lorebook', 'asset', 'script', "
                    "or 'other' (any other free-text field of the card).",
    )
    source_item_id: str | None = Field(
        default=None, description="Traceability only - e.g. the lorebook entry id/name this came from.",
    )


class ImageLinkExtraction(BaseModel):
    candidates: list[ImageUrlCandidate] = Field(default_factory=list)


def _find_urls(text: str) -> list[str]:
    if not text:
        return []
    found = []
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
        if url:
            found.append(url)
    return found


class ImageLinkExtractor:
    """Stage: pure text scan, no I/O, no LLM - a peer of `CardPreprocessor`/`WorldAssembler`."""

    @staticmethod
    def extract(card: SillyTavernCardV3) -> ImageLinkExtraction:
        data = card.data
        seen: set[str] = set()
        candidates: list[ImageUrlCandidate] = []

        def add(url: str, source: str, source_item_id: str | None = None) -> None:
            if url in seen:
                return
            seen.add(url)
            candidates.append(ImageUrlCandidate(url=url, source=source, source_item_id=source_item_id))

        for url in _find_urls(data.first_mes):
            add(url, "first_message")

        book = data.character_book
        if book:
            for entry in book.entries:
                if not entry.enabled:
                    continue
                entry_id = str(entry.id) if entry.id is not None else (entry.comment or entry.name)
                for url in _find_urls(entry.content):
                    add(url, "lorebook", entry_id)

        for asset in data.assets or []:
            if asset.uri.startswith("http://") or asset.uri.startswith("https://"):
                add(asset.uri, "asset", asset.name)

        if data.extensions:
            try:
                serialized = json.dumps(data.extensions, ensure_ascii=False)
            except TypeError:
                serialized = ""
            for url in _find_urls(serialized):
                add(url, "script")

        # Catch-all: every other free-text field of the card, whatever it's called - see module
        # docstring. Dedup via `add()` means anything already found above isn't reported twice.
        # Disabled lorebook entries are stripped first - the user turned that entry off, so its
        # content shouldn't surface image links any more than the labelled lorebook scan above
        # (which also skips disabled entries) would.
        catchall_data = data
        if book and any(not entry.enabled for entry in book.entries):
            catchall_data = data.model_copy(update={
                "character_book": book.model_copy(update={
                    "entries": [entry for entry in book.entries if entry.enabled],
                }),
            })

        try:
            everything = json.dumps(catchall_data.model_dump(mode="json"), ensure_ascii=False)
        except TypeError:
            everything = ""
        for url in _find_urls(everything):
            add(url, "other")

        return ImageLinkExtraction(candidates=candidates)
