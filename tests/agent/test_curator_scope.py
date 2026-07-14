import pytest

from opensprite.documents.curator import CURATOR_SCOPE_CHOICES as legacy_scope_choices
from opensprite.documents.curator import resolve_curator_scope as legacy_resolve_curator_scope
from opensprite.documents.curator_scope import (
    CURATOR_MAINTENANCE_JOB_KEYS,
    CURATOR_SCOPE_CHOICES,
    _ordered_maintenance_job_keys,
    resolve_curator_scope,
)


def test_resolve_curator_scope_defaults_to_all_jobs_and_skills():
    assert resolve_curator_scope(None) == (CURATOR_MAINTENANCE_JOB_KEYS, True)
    assert resolve_curator_scope("") == (CURATOR_MAINTENANCE_JOB_KEYS, True)


def test_resolve_curator_scope_handles_named_scopes():
    assert resolve_curator_scope("maintenance") == (CURATOR_MAINTENANCE_JOB_KEYS, False)
    assert resolve_curator_scope("skills") == ((), True)
    assert resolve_curator_scope("memory") == (("memory",), False)


def test_resolve_curator_scope_rejects_unknown_scopes():
    with pytest.raises(ValueError, match="Unknown curator scope: nope"):
        resolve_curator_scope("nope")


def test_ordered_maintenance_job_keys_keeps_canonical_order():
    assert _ordered_maintenance_job_keys(["user_profile", "memory", "missing", "memory"]) == (
        "memory",
        "user_profile",
    )


def test_curator_reexports_scope_helpers_for_compatibility():
    assert legacy_scope_choices is CURATOR_SCOPE_CHOICES
    assert legacy_resolve_curator_scope is resolve_curator_scope
