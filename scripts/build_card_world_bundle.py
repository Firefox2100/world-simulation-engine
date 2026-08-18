"""
Convert one SillyTavern character card into a "world bundle" evaluation test asset - the same
format tests/evaluation_test/world_fixtures.py loads (see that module's docstring) - by running it
through the real production extraction pipeline (WorldReconstructor, the same code the
/worlds/import/sillytavern/extract endpoint uses) and writing its in-memory result straight to
bundle files. There is no import/export round-trip: `AssembledWorld.world`/`.sections` are already
shaped exactly like WorldExportService's `world.json`/`data/*.jsonl` (see world_assembler.py's
`assemble()`), so this script writes them directly.

*** This calls a real LLM (once per extraction stage - a dozen or more calls). Claude must never
run this script (CLAUDE.md hard rule 1) - you run it yourself, once per card you want to add as an
evaluation world. ***

Needs no Neo4j and no app-level (WSE_NEO4J_*) configuration at all - the extraction pipeline's only
database touchpoint is resolving a chat model config, which this script supplies directly from a
fixed in-memory config instead of a real ConfigStore lookup. That config is built from the same
WSE_EVAL_* environment variables (WSE_EVAL_LLM_PROVIDER, WSE_EVAL_CHAT_MODEL, WSE_EVAL_LLM_BASE_URL,
etc. - see tests/evaluation_test/eval_llm_config.py) the evaluation_test suite itself reads, so the
same tests/.env you already use to run `pytest tests/evaluation_test` also works here - no separate
setup needed. Every extraction stage uses the one WSE_EVAL_CHAT_MODEL, unlike the real app where
each pipeline component can have its own configured model.

Output lands under tests/evaluation_test/worlds/<slug>/ by default, where
tests/evaluation_test/worlds/.gitignore excludes every world except an explicit allow-list
(CLAUDE.md hard rule 2 - a SillyTavern card's content is licensed and must never be committed by
accident). To check a specific generated world into git anyway, add its own `!<slug>/` and
`!<slug>/**` pair to that .gitignore, mirroring the existing blackwater_observatory entries.

The generated bundle's eval/scenarios.json is an empty skeleton (every category present, all
empty) - this script has no way to author meaningful "intended input" test cases for a card it has
never seen played out, so the workflow eval tests simply run zero cases against this world until
you hand-author some, the same way a world with no cases for a category always behaves.

Example:
    source .venv/bin/activate
    python scripts/build_card_world_bundle.py

Or convert one card only:
    python scripts/build_card_world_bundle.py tests/evaluation_test/assets/st-cards/01.en.png
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVAL_TEST_DIR = ROOT / "tests" / "evaluation_test"
if str(EVAL_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_TEST_DIR))

from world_simulation_engine.component.sillytavern_converter import (  # noqa: E402
    AssembledWorld, DataExtractor, WorldReconstructor,
)
from world_simulation_engine.misc.enums import SupportedLanguage  # noqa: E402
from world_simulation_engine.model import Author  # noqa: E402
from world_simulation_engine.service.world_bundle_spec import WORLD_BUNDLE_SPEC, WORLD_BUNDLE_SPEC_VERSION  # noqa: E402

from eval_llm_config import build_evaluation_chat_model_config, build_evaluation_connection_config  # noqa: E402

DEFAULT_WORLDS_DIR = ROOT / "tests" / "evaluation_test" / "worlds"
DEFAULT_CARDS_DIR = ROOT / "tests" / "evaluation_test" / "assets" / "st-cards"

_SCENARIO_CATEGORIES = (
    "synthetic_coordination_cases",
    "input_pipeline_cases",
    "action_validator_evaluation_cases",
    "user_coordination_cases",
    "character_simulator_cases",
    "emotion_updater_cases",
    "subjective_model_updater_cases",
    "relationship_updater_cases",
    "objective_relationship_validation_cases",
    "world_simulator_cases",
)


class _StaticChatConfigStore:
    """Stands in for `ConfigStore` - the pipeline only ever calls `get_global_chat`/
    `get_connection_by_source` (see `SillyTavernPipelineComponent._prepare_global_llm_service`),
    and every stage should use the one WSE_EVAL_* model regardless of which ComponentType asks."""

    def __init__(self, chat_config, connection_config):
        self._chat_config = chat_config
        self._connection_config = connection_config

    async def get_global_chat(self, _component):
        return self._chat_config

    async def get_connection_by_source(self, *, source_id):  # noqa: ARG002 - fixed stub
        return self._connection_config


class _StaticChatDatabase:
    """Stands in for `DatabaseService` - only the `.config` attribute is ever touched by the
    extraction pipeline (verified: no `component/sillytavern_converter/*.py` file calls anything
    else on `self._db`)."""

    def __init__(self, chat_config, connection_config):
        self.config = _StaticChatConfigStore(chat_config, connection_config)


def build_bundle(
        *,
        card_path: Path,
        language: SupportedLanguage,
        output_dir: Path,
        author_name: str,
) -> AssembledWorld:
    connection_config = build_evaluation_connection_config()
    chat_config = build_evaluation_chat_model_config(connection_config)
    database = _StaticChatDatabase(chat_config, connection_config)

    card_bytes = card_path.read_bytes()
    extracted = DataExtractor().extract(card_bytes)

    model_name: str = chat_config.model
    print(
        f"Extracting {card_path.name} ({language.value}) with {model_name!r}... "
        "this calls a real LLM many times."
    )

    async def _run() -> AssembledWorld:
        return await WorldReconstructor(database=database).reconstruct_from_card(
            extracted.card, language=language,
        )

    assembled = asyncio.run(_run())
    for note in assembled.report.entries:
        marker = "!" if note.low_confidence else "-"
        print(f"  {marker} {note.message}")

    author = Author(name=author_name)
    _write_bundle(assembled, author=author, output_dir=output_dir)
    _write_eval_extras(output_dir, source_card=card_path.name, language=language)
    return assembled


def _write_bundle(assembled: AssembledWorld, *, author: Author, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "data").mkdir(parents=True)

    (output_dir / "author.json").write_text(
        json.dumps(author.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8",
    )

    world_row = dict(assembled.world)
    world_row["author_id"] = author.id
    (output_dir / "world.json").write_text(
        json.dumps(world_row, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    for section_name, rows in assembled.sections.items():
        _write_jsonl(output_dir / "data" / f"{section_name}.jsonl", rows)

    manifest = {
        "spec": WORLD_BUNDLE_SPEC,
        "spec_version": WORLD_BUNDLE_SPEC_VERSION,
        "generated_by": "scripts/build_card_world_bundle.py",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_eval_extras(output_dir: Path, *, source_card: str, language: SupportedLanguage) -> None:
    world_row = json.loads((output_dir / "world.json").read_text(encoding="utf-8"))
    character_rows = _read_jsonl(output_dir / "data" / "characters.jsonl")

    eval_dir = output_dir / "eval"
    eval_dir.mkdir(exist_ok=True)

    (eval_dir / "simulation.json").write_text(
        json.dumps(
            {
                "id": str(uuid4()),
                "name": world_row["name"],
                "description": world_row.get("description"),
                "current_time": world_row["starting_time"],
                "emotion_enabled": True,
                "suggested_actions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Neutral baseline for every extracted character - emotions are never part of a world export
    # (they're simulation-runtime state, see world_fixtures.py's docstring), and this script has
    # no basis to guess a non-neutral starting mood for a character it has never seen played out.
    emotion_rows = [
        json.dumps({
            "character_id": row["id"],
            "baseline": {"valence": 0.0, "arousal": 0.0, "dominance": 0.0, "dimensions": {}},
        }, ensure_ascii=False)
        for row in character_rows
    ]
    (eval_dir / "character_emotions.jsonl").write_text(
        "\n".join(emotion_rows) + ("\n" if emotion_rows else ""), encoding="utf-8",
    )

    (eval_dir / "scenarios.json").write_text(
        json.dumps({category: [] for category in _SCENARIO_CATEGORIES}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_card"] = source_card
    manifest["extraction_language"] = language.value
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "card", type=Path, nargs="?",
        help=(
            "Path to one SillyTavern character card (.png or .json). If omitted, all cards under "
            "tests/evaluation_test/assets/st-cards are converted."
        ),
    )
    parser.add_argument(
        "--language", choices=[lang.value for lang in SupportedLanguage], default=None,
        help=(
            "Extraction language override. By default it is inferred from the card filename's final "
            "dot-segment (for example, 01.en.png selects 'en')."
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output bundle directory. Defaults to tests/evaluation_test/worlds/<card stem>/.",
    )
    parser.add_argument(
        "--author-name", default="Card World Bundle Generator",
        help="Author name to attribute the generated world to.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.card is None:
        if args.output is not None:
            raise SystemExit("--output can only be used when converting a single card.")
        card_paths = sorted(
            path for path in DEFAULT_CARDS_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".json"}
        ) if DEFAULT_CARDS_DIR.is_dir() else []
        if not card_paths:
            raise SystemExit(f"No .png or .json cards found in {DEFAULT_CARDS_DIR}.")
    else:
        card_paths = [args.card]

    for card_path in card_paths:
        output_dir = args.output or (DEFAULT_WORLDS_DIR / card_path.stem)
        language_code = args.language or card_path.stem.rsplit(".", 1)[-1]
        try:
            language = SupportedLanguage(language_code)
        except ValueError as exc:
            supported = " or ".join(f".{language.value}" for language in SupportedLanguage)
            raise SystemExit(
                f"Cannot infer extraction language from {card_path.name!r}: expected the filename "
                f"to end in {supported} before its extension, or pass --language explicitly."
            ) from exc

        build_bundle(
            card_path=card_path,
            language=language,
            output_dir=output_dir,
            author_name=args.author_name,
        )
        print(f"Wrote world bundle to {output_dir}")

    print(
        "eval/scenarios.json is an empty skeleton - hand-author 'intended input' cases there for "
        "the workflow eval tests to exercise this world (see tests/evaluation_test/worlds/"
        "blackwater_observatory/eval/scenarios.json for the shape). This directory is gitignored "
        "by default (CLAUDE.md hard rule 2) - see tests/evaluation_test/worlds/.gitignore if you "
        "want to check it in anyway."
    )


if __name__ == "__main__":
    main()
