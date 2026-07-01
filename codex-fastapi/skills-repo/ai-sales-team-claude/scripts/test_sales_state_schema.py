#!/usr/bin/env python3
"""Tests for sales-state schema validation."""

import unittest
from pydantic import ValidationError

from sales_state_schema import SalesQualifyState


VALID_STATE = {
    "company": "Latent HQ",
    "url": "https://latenthq.com/",
    "date": "2026-06-16",
    "stage": "pending_qualify_review_low_score",
    "lead_grade": "D",
    "qualification_gate_score": 29,
    "qualification_gate_basis": "bant_total",
    "scores": {
        "budget": 7,
        "authority": 15,
        "need": 4,
        "timeline": 3,
        "bant_total": 29,
        "meddic_fit": 34,
        "opportunity_quality_score": 34,
    },
    "approval_required": "qualify_review",
    "artifacts": {"lead_qualification": "LEAD-QUALIFICATION.md"},
    "send_ready": False,
    "blocked_reason": "Qualification score below automation threshold",
    "next_action": "Human Qualify Approval: Approve / Reject / Skip",
    "signals": {
        "company_type": "healthcare software development agency",
        "size": "11-50 employees",
        "budget_signal": "weak to moderate",
        "authority_signal": "moderate",
        "need_signal": "weak",
        "timeline_signal": "weak",
    },
    "sources": ["https://www.latenthq.com/"],
    "last_updated": "2026-06-16",
}


class SalesQualifyStateTests(unittest.TestCase):
    def test_valid_state_passes(self):
        state = SalesQualifyState.model_validate(VALID_STATE)
        self.assertEqual(state.qualification_gate_score, 29)

    def test_rejects_drifted_key_names(self):
        drifted = {
            "company": "Latent HQ",
            "website": "https://latenthq.com/",
            "stage": "nurture",
            "qualification_artifact": "LEAD-QUALIFICATION.md",
            "scores": {
                "budget": 7,
                "authority": 15,
                "need": 4,
                "timeline": 3,
                "bant_total": 29,
                "meddic_fit": 34,
            },
            "send_ready": False,
            "blockers": [],
            "source_urls": ["https://www.latenthq.com/"],
        }
        with self.assertRaises(ValidationError):
            SalesQualifyState.model_validate(drifted)

    def test_gate_score_must_match_bant_total(self):
        bad = dict(VALID_STATE)
        bad["qualification_gate_score"] = 30
        with self.assertRaises(ValidationError):
            SalesQualifyState.model_validate(bad)

    def test_low_score_requires_low_score_stage(self):
        bad = dict(VALID_STATE)
        bad["stage"] = "qualified_pending_review"
        with self.assertRaises(ValidationError):
            SalesQualifyState.model_validate(bad)


if __name__ == "__main__":
    unittest.main()
