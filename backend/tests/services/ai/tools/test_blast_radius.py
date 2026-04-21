"""BlastRadius dataclass + requires_approval() + reasons()."""
from __future__ import annotations

from uuid import uuid4
import pytest
from app.services.ai.actions.blast_radius import BlastRadius


def test_internal_single_reversible_no_money_is_auto():
    br = BlastRadius(audience='internal', fires_external_effect=False,
                     financial_dollar_amount=None, scope_size=1)
    assert br.requires_approval() is False
    assert br.reasons() == []


def test_external_audience_requires_approval():
    br = BlastRadius(audience='external', fires_external_effect=False,
                     financial_dollar_amount=None, scope_size=1)
    assert br.requires_approval() is True
    assert "outside Rex Construction" in br.reasons()[0]


def test_external_effect_flag_requires_approval():
    br = BlastRadius(audience='internal', fires_external_effect=True,
                     financial_dollar_amount=None, scope_size=1)
    assert br.requires_approval() is True
    assert "external system" in br.reasons()[0].lower()


def test_any_positive_money_requires_approval():
    br = BlastRadius(audience='internal', fires_external_effect=False,
                     financial_dollar_amount=0.01, scope_size=1)
    assert br.requires_approval() is True


def test_zero_dollars_does_not_trigger():
    br = BlastRadius(audience='internal', fires_external_effect=False,
                     financial_dollar_amount=0.0, scope_size=1)
    assert br.requires_approval() is False


def test_batch_of_five_requires_approval():
    br = BlastRadius(audience='internal', fires_external_effect=False,
                     financial_dollar_amount=None, scope_size=5)
    assert br.requires_approval() is True
    assert "batch of 5" in br.reasons()[0]


def test_multiple_reasons_all_listed():
    br = BlastRadius(audience='external', fires_external_effect=True,
                     financial_dollar_amount=100.0, scope_size=7)
    reasons = br.reasons()
    assert len(reasons) == 4


def test_frozen_dataclass():
    br = BlastRadius(audience='internal', fires_external_effect=False,
                     financial_dollar_amount=None, scope_size=1)
    with pytest.raises(Exception):
        br.audience = 'external'


def test_to_jsonb_roundtrip():
    original = BlastRadius(audience='external', fires_external_effect=True,
                           financial_dollar_amount=42.5, scope_size=3)
    payload = original.to_jsonb()
    restored = BlastRadius.from_jsonb(payload)
    assert restored == original
