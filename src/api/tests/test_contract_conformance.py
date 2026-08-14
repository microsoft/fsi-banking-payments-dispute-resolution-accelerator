"""
test_contract_conformance.py

Verifies:
  1. Every synthetic case JSON validates against case.schema.json.
  2. Python Case/Deadline dataclasses can be instantiated from each fixture.
  3. CaseSummary projection produced by case_store._to_summary() contains all
     required fields and only schema-legal values.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

import pytest
from jsonschema import Draft202012Validator, ValidationError

from models.case import (
    Case,
    CaseSummary,
    CaseSummaryDeadline,
    Deadline,
    Evidence,
    EvidenceGap,
    ReasonCodeChecklistItem,
    RebuttalDraft,
    Citation,
)
from services.case_store import _to_summary

# ── Load schema and wire validator once per session ───────────────────────────

@pytest.fixture(scope="session")
def validator(schema):
    return Draft202012Validator(schema)


# ── 1. JSON Schema conformance ────────────────────────────────────────────────

def pytest_generate_tests(metafunc):
    """Dynamically parametrize schema-conformance tests with actual case files."""
    if "fname" in metafunc.fixturenames and "case_dict" in metafunc.fixturenames:
        cases_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "src", "data", "synthetic", "cases"
        )
        # Normalise — tests/ lives inside src/api/tests/
        # conftest exposes SYNTHETIC_CASES_DIR but we recompute cleanly here
        api_tests_dir = os.path.dirname(os.path.abspath(__file__))
        api_dir = os.path.dirname(api_tests_dir)
        src_dir = os.path.dirname(api_dir)
        cases_dir = os.path.join(src_dir, "data", "synthetic", "cases")

        params = []
        for fname in sorted(os.listdir(cases_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(cases_dir, fname), encoding="utf-8") as fh:
                    params.append(pytest.param(fname, json.load(fh), id=fname))
        metafunc.parametrize("fname,case_dict", params)


class TestSchemaConformance:
    def test_case_validates_against_schema(self, fname, case_dict, validator):
        """Every synthetic case JSON must be valid against case.schema.json."""
        errors = list(validator.iter_errors(case_dict))
        assert errors == [], (
            f"{fname} has {len(errors)} schema violation(s):\n"
            + "\n".join(f"  • {e.json_path}: {e.message}" for e in errors[:5])
        )

    def test_required_top_level_fields_present(self, fname, case_dict):
        required = {"caseId", "status", "reasonCode", "deadline", "createdAt"}
        missing = required - set(case_dict.keys())
        assert not missing, f"{fname} missing required fields: {missing}"

    def test_status_is_valid_enum(self, fname, case_dict):
        valid_statuses = {
            "intake", "evidence_gathering", "ai_drafting", "pending_review",
            "approved", "denied", "escalated", "submitted", "expired",
        }
        assert case_dict["status"] in valid_statuses, (
            f"{fname}: unexpected status '{case_dict['status']}'"
        )

    def test_deadline_shape(self, fname, case_dict):
        dl = case_dict["deadline"]
        assert "dueDate" in dl, f"{fname}: deadline missing dueDate"
        assert "daysRemaining" in dl, f"{fname}: deadline missing daysRemaining"
        assert "network" in dl, f"{fname}: deadline missing network"
        assert isinstance(dl["daysRemaining"], int), f"{fname}: daysRemaining must be int"


# ── 2. Python model round-trip ────────────────────────────────────────────────

class TestPythonModelRoundTrip:
    def test_deadline_dataclass(self, fname, case_dict):
        dl = case_dict["deadline"]
        obj = Deadline(
            network=dl["network"],
            dueDate=dl["dueDate"],
            daysRemaining=dl["daysRemaining"],
        )
        assert obj.dueDate == dl["dueDate"]
        assert obj.daysRemaining == dl["daysRemaining"]

    def test_case_required_fields(self, fname, case_dict):
        """Case dataclass can be instantiated with the required fields from every fixture."""
        dl = case_dict["deadline"]
        deadline_obj = Deadline(
            network=dl["network"],
            dueDate=dl["dueDate"],
            daysRemaining=dl["daysRemaining"],
        )
        case = Case(
            caseId=case_dict["caseId"],
            status=case_dict["status"],
            reasonCode=case_dict["reasonCode"],
            deadline=deadline_obj,
            createdAt=case_dict["createdAt"],
        )
        assert case.caseId == case_dict["caseId"]
        assert case.status == case_dict["status"]

    def test_evidence_items_round_trip(self, fname, case_dict):
        for ev in case_dict.get("evidence", []):
            obj = Evidence(
                evidenceId=ev["evidenceId"],
                type=ev["type"],
                sourceSystem=ev["sourceSystem"],
                retrievedAt=ev["retrievedAt"],
                contentRef=ev["contentRef"],
                completeness=ev["completeness"],
            )
            assert obj.evidenceId == ev["evidenceId"]
            assert obj.completeness in ("complete", "partial", "missing")

    def test_evidence_gap_round_trip(self, fname, case_dict):
        for gap in case_dict.get("evidenceGaps", []):
            obj = EvidenceGap(
                missingItem=gap["missingItem"],
                reason=gap["reason"],
                impact=gap["impact"],
            )
            assert obj.impact in ("critical", "high", "medium", "low")

    def test_checklist_round_trip(self, fname, case_dict):
        for item in case_dict.get("reasonCodeChecklist", []):
            obj = ReasonCodeChecklistItem(
                item=item["item"],
                required=item["required"],
                satisfied=item["satisfied"],
            )
            assert isinstance(obj.required, bool)
            assert isinstance(obj.satisfied, bool)


# ── 3. CaseSummary projection ─────────────────────────────────────────────────

SUMMARY_REQUIRED_FIELDS = {"caseId", "status", "reasonCode", "deadline", "createdAt"}
SUMMARY_DEADLINE_FIELDS = {"dueDate", "daysRemaining"}


class TestCaseSummaryProjection:
    def test_summary_has_required_fields(self, fname, case_dict):
        summary = _to_summary(case_dict)
        missing = SUMMARY_REQUIRED_FIELDS - set(summary.keys())
        assert not missing, f"{fname} summary missing: {missing}"

    def test_summary_deadline_subset(self, fname, case_dict):
        summary = _to_summary(case_dict)
        dl = summary["deadline"]
        assert set(dl.keys()) == SUMMARY_DEADLINE_FIELDS, (
            f"{fname}: summary deadline should have exactly {SUMMARY_DEADLINE_FIELDS}, got {set(dl.keys())}"
        )

    def test_summary_no_full_deadline_network(self, fname, case_dict):
        """CaseSummary deadline must NOT include 'network' (queue-list subset)."""
        summary = _to_summary(case_dict)
        assert "network" not in summary["deadline"], (
            f"{fname}: CaseSummary deadline must omit 'network'"
        )

    def test_summary_win_probability_range(self, fname, case_dict):
        summary = _to_summary(case_dict)
        wp = summary.get("winProbability")
        if wp is not None:
            assert 0.0 <= wp <= 1.0, f"{fname}: winProbability {wp} out of [0,1]"
