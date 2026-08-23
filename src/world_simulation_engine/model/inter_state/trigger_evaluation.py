"""LLM output schema for batch-checking a bounded set of semantic trigger conditions against one
turn's narration and newly committed memories - see component/simulator/trigger_evaluator.py.

Only a SemanticCondition's own `statement` is ever fed to this evaluator (never a trigger's name,
description, or effect), and the output carries nothing back but a verdict per candidate index.
"""

from pydantic import BaseModel, ConfigDict, Field


class SemanticConditionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(description="Index into the supplied candidates list.")
    satisfied: bool
    reason: str = Field(min_length=1, description="One short sentence grounding the verdict in what was supplied.")


class SemanticConditionEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[SemanticConditionVerdict] = Field(default_factory=list, max_length=6)
