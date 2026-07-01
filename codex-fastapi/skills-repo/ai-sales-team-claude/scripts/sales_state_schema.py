#!/usr/bin/env python3
"""Sales state schemas and validators.

This module is the source of truth for machine-readable state files emitted by
AI Sales Team skills. It currently defines the /sales qualify state contract.

Usage:
    python3 scripts/sales_state_schema.py validate sales-state.json
    python3 scripts/sales_state_schema.py export-schema schemas/sales-qualify-state.schema.json
    cat sales-state.json | python3 scripts/sales_state_schema.py validate -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class QualifyScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget: int = Field(ge=0, le=25)
    authority: int = Field(ge=0, le=25)
    need: int = Field(ge=0, le=25)
    timeline: int = Field(ge=0, le=25)
    bant_total: int = Field(ge=0, le=100)
    meddic_fit: int = Field(ge=0, le=100)
    opportunity_quality_score: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def bant_total_matches_dimensions(self) -> "QualifyScores":
        expected = self.budget + self.authority + self.need + self.timeline
        if self.bant_total != expected:
            raise ValueError(
                f"scores.bant_total must equal budget + authority + need + timeline ({expected})"
            )
        return self


class QualifySignals(BaseModel):
    model_config = ConfigDict(extra="allow")

    company_type: str
    size: str
    budget_signal: Literal["strong", "moderate", "weak", "unknown", "weak to moderate", "moderate to strong"]
    authority_signal: Literal["strong", "moderate", "weak", "unknown", "weak to moderate", "moderate to strong"]
    need_signal: Literal["strong", "moderate", "weak", "unknown", "weak to moderate", "moderate to strong"]
    timeline_signal: Literal["strong", "moderate", "weak", "unknown", "weak to moderate", "moderate to strong"]


class QualifyArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_qualification: Literal["LEAD-QUALIFICATION.md"]


class SalesQualifyState(BaseModel):
    """Stable state contract for /sales qualify automation output."""

    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1)
    url: str = Field(min_length=1)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    stage: Literal["qualified_pending_review", "pending_qualify_review_low_score"]
    lead_grade: Literal["A", "B", "C", "D"]
    qualification_gate_score: int = Field(ge=0, le=100)
    qualification_gate_basis: Literal["bant_total"]
    scores: QualifyScores
    approval_required: Literal["qualify_review"]
    artifacts: QualifyArtifacts
    send_ready: Literal[False]
    blocked_reason: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    signals: QualifySignals
    sources: list[str] = Field(default_factory=list)
    last_updated: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def gate_score_matches_bant(self) -> "SalesQualifyState":
        if self.qualification_gate_score != self.scores.bant_total:
            raise ValueError("qualification_gate_score must equal scores.bant_total")
        if self.qualification_gate_score < 40 and self.stage != "pending_qualify_review_low_score":
            raise ValueError("stage must be pending_qualify_review_low_score when qualification_gate_score < 40")
        if self.qualification_gate_score >= 40 and self.stage != "qualified_pending_review":
            raise ValueError("stage must be qualified_pending_review when qualification_gate_score >= 40")
        return self


def load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_file(path: str) -> SalesQualifyState:
    return SalesQualifyState.model_validate(load_json(path))


def export_schema(path: str) -> None:
    schema = SalesQualifyState.model_json_schema()
    output = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if path == "-":
        sys.stdout.write(output)
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or export AI Sales Team state schemas.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate a /sales qualify sales-state.json file")
    validate.add_argument("path", help="Path to JSON file, or - for stdin")

    export = sub.add_parser("export-schema", help="Export the /sales qualify JSON Schema")
    export.add_argument("path", help="Output path, or - for stdout")

    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_file(args.path)
            print("valid")
        elif args.command == "export-schema":
            export_schema(args.path)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
