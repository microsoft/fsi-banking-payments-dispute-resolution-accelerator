"""
conftest.py — shared fixtures for the disputes API test suite.

No azure.functions.Blueprint monkey-patching here.  The production modules
(dispute_orchestrator, case_activities, case_actions) must use
azure.durable_functions.Blueprint (df.Blueprint) directly so that
orchestration_trigger / activity_trigger / durable_client_input resolve
natively — exactly as the Azure Functions host would load them.
"""
from __future__ import annotations

import json
import os

import pytest

# ── Path constants ────────────────────────────────────────────────────────────
# conftest.py lives at src/api/tests/conftest.py
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_API_DIR = os.path.dirname(_TESTS_DIR)
_SRC_DIR = os.path.dirname(_API_DIR)
_REPO_ROOT = os.path.dirname(_SRC_DIR)

SCHEMA_PATH = os.path.join(_SRC_DIR, "shared", "schemas", "case.schema.json")
SYNTHETIC_CASES_DIR = os.path.join(_SRC_DIR, "data", "synthetic", "cases")
WEB_DIR = os.path.join(_SRC_DIR, "web")


# ── Session-scoped fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def schema():
    """Parsed case.schema.json."""
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def case_files():
    """List of (filename, parsed-dict) tuples for all synthetic case JSON files."""
    result = []
    for fname in sorted(os.listdir(SYNTHETIC_CASES_DIR)):
        if fname.endswith(".json"):
            fpath = os.path.join(SYNTHETIC_CASES_DIR, fname)
            with open(fpath, encoding="utf-8") as fh:
                result.append((fname, json.load(fh)))
    return result


# ── Function-scoped fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_case_store_cache():
    """
    Clear the LRU cache on case_store._load_all before and after each test
    so tests are isolated from each other and from module-level state.
    """
    from services import case_store
    case_store._load_all.cache_clear()
    yield
    case_store._load_all.cache_clear()


@pytest.fixture
def known_case_id():
    """The caseId of a known synthetic case (Visa 13.1 / bd3f6fe3)."""
    return "bd3f6fe3-ad20-5e96-b926-da3b87c18834"


@pytest.fixture
def unknown_case_id():
    return "00000000-0000-0000-0000-000000000000"
