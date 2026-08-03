"""Live entity cross-references inside stored free text, e.g. `{{ character['id'].name }}`.

SillyTavern cards lean on template macros (`{{char}}`, `{{user}}`) so one character's text can
refer to another by name. Baking a literal name into stored text at import time would go stale the
moment a user renames anyone afterward, so this renders lazily, at the point text is used, against
whatever the current roster looks like.

The placeholder surface is deliberately narrow: only `id`/`name`, never traits, state, or
narrative content. There is no reason for one entity's stored text to pull in another entity's
personality or private state, and exposing more than identity here would let unrelated fields leak
across entities through template text alone.
"""

from jinja2 import ChainableUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ConfigDict, Field

# ChainableUndefined lets a missing id or group (`character['unknown_id'].name`) resolve through
# the whole attribute chain instead of raising partway through - so one stale reference renders as
# empty text without discarding everything else already resolved in the same string.
_ENV = SandboxedEnvironment(undefined=ChainableUndefined)


class PlaceholderEntity(BaseModel):
    """Identity-only cross-reference: what a placeholder is allowed to expose about an entity."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class PlaceholderContext(BaseModel):
    """Entities addressable from placeholder text, grouped by kind and keyed by id."""

    model_config = ConfigDict(extra="forbid")

    character: dict[str, PlaceholderEntity] = Field(default_factory=dict)
    background_character: dict[str, PlaceholderEntity] = Field(default_factory=dict)
    location: dict[str, PlaceholderEntity] = Field(default_factory=dict)
    landmark: dict[str, PlaceholderEntity] = Field(default_factory=dict)
    item: dict[str, PlaceholderEntity] = Field(default_factory=dict)
    equipment: dict[str, PlaceholderEntity] = Field(default_factory=dict)
    container: dict[str, PlaceholderEntity] = Field(default_factory=dict)

    def add(self, group: str, *, id: str, name: str) -> None:  # noqa: A002 - matches the model field name
        getattr(self, group)[id] = PlaceholderEntity(id=id, name=name)


def render_placeholders(text: str, context: PlaceholderContext) -> str:
    """Resolve `{{ character['id'].name }}`-style references against a live entity roster.

    A reference to an id or group absent from `context` (never registered, since deleted, or
    blocked by the sandbox as unsafe) resolves to an empty string in place, rather than raising -
    one stale or malicious reference should not discard everything else already resolved in the
    same string. Malformed template syntax (e.g. unbalanced `{{`) instead fails the whole render
    and returns `text` unchanged, since there is no partial result to preserve in that case. Text
    with no `{{`/`{%` is returned as-is without invoking the template engine at all.
    """
    if "{{" not in text and "{%" not in text:
        return text

    try:
        template = _ENV.from_string(text)
        return template.render(**context.model_dump())
    except TemplateError:
        return text
