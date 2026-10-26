"""Red/Green suite proving the Fact-Fetching Boundary.

Baseline  = the agent's beliefs go straight into the DMN as "facts" (vulnerable).
Protected = the Boundary replaces beliefs with facts from the System of Record.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from boundary_agent.boundary import compose
from boundary_agent.contracts.models import (
    AgentIntent,
    AuthorizationError,
    ClaimedFacts,
    DecisionRequest,
    GrantError,
    Outcome,
    TriggerBindingError,
    TriggerContext,
    utcnow,
)
from boundary_agent.executor.apply import apply_discount
from boundary_agent.utils import clients, grant_store

STANDARD_TRIGGER = dict(account_id="ACC-001", actor_id="sales-agent-bot")


# ----------------------------------------------------------------- Scenario 1


def test_scenario1_baseline_claimed_premium_bypasses_policy():
    """RED: agent writes its own claim into `facts` and the DMN happily approves 20%."""
    payload = {
        "facts": {"tier": "premium", "margin_pct": 20.0, "credit_hold": False},
        "intent": {"proposed_discount_pct": 20, "claimed_facts": {"tier": "premium"}},
    }
    raw = clients.evaluate_raw(payload)
    assert raw["DiscountApproval"]["Outcome"] == "APPROVED"
    assert raw["DiscountApproval"]["Reason Code"] == "WITHIN_ENTITLEMENT"
    assert raw["EntitledMaxDiscount"] == 20


def test_scenario1_protected_claimed_premium_goes_to_review():
    """GREEN: same claim, but the Boundary fetches tier=standard from the CRM."""
    intent = AgentIntent(customer_ref="alice@example.com", proposed_discount_pct=20,
                         claimed_facts=ClaimedFacts(tier="premium"))
    trigger = TriggerContext(**STANDARD_TRIGGER)

    request = compose.compose_decision_request(intent, trigger)
    assert request.facts.tier == "standard"            # real fact won over the claim
    assert request.intent.claimed_facts.tier == "premium"  # claim preserved as *intent*

    response = compose.evaluate(request)
    assert response.outcome is Outcome.REVIEW
    assert response.reason_code == "ESCALATION_EXCEEDS_ENTITLEMENT"
    assert response.claim_escalation is True
    assert response.entitled_max_discount == 10

    with pytest.raises(GrantError):
        compose.issue_grant(response, trigger)


# ----------------------------------------------------------------- Scenario 2


def test_scenario2_id_spoofing_raises_trigger_binding_error_before_any_fetch():
    """Agent points at the premium account while the trigger is bound to the standard one."""
    intent = AgentIntent(customer_ref="ACC-002", proposed_discount_pct=20,
                         claimed_facts=ClaimedFacts(tier="premium"))
    trigger = TriggerContext(**STANDARD_TRIGGER)

    with patch.object(clients, "fetch_facts", wraps=clients.fetch_facts) as fetch, \
         patch.object(clients, "evaluate_raw", wraps=clients.evaluate_raw) as dmn:
        with pytest.raises(TriggerBindingError):
            compose.compose_decision_request(intent, trigger)
        fetch.assert_not_called()
        dmn.assert_not_called()


# ----------------------------------------------------------------- Contract hardening


def test_agent_cannot_smuggle_facts_into_intent():
    with pytest.raises(ValidationError):
        AgentIntent(customer_ref="alice", proposed_discount_pct=20,
                    facts={"tier": "premium"})  # type: ignore[call-arg]


def test_decision_request_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate({
            "facts": {"tier": "standard", "margin_pct": 20.0, "credit_hold": False},
            "intent": {"proposed_discount_pct": 20, "claimed_facts": {}},
            "override": True,
        })


def test_unauthorized_actor_is_rejected_before_binding():
    intent = AgentIntent(customer_ref="ACC-002", proposed_discount_pct=5)
    trigger = TriggerContext(account_id="ACC-002", actor_id="support-agent-bot")
    with patch.object(clients, "resolve_ref", wraps=clients.resolve_ref) as resolve:
        with pytest.raises(AuthorizationError):
            compose.compose_decision_request(intent, trigger)
        resolve.assert_not_called()


# ----------------------------------------------------------------- Executor / grant


def _approved_grant():
    intent = AgentIntent(customer_ref="alice@example.com", proposed_discount_pct=10,
                         claimed_facts=ClaimedFacts(tier="premium"))
    trigger = TriggerContext(**STANDARD_TRIGGER)
    response = compose.run_protected(intent, trigger)
    assert response.outcome is Outcome.APPROVED
    assert response.reason_code == "WITHIN_ENTITLEMENT_ESCALATION_LOGGED"
    return compose.issue_grant(response, trigger)


def test_grant_is_single_use_and_timezone_aware():
    grant = _approved_grant()
    assert grant.expires_at.tzinfo is not None and grant.issued_at.utcoffset().total_seconds() == 0

    result = apply_discount(grant.grant_id, "sales-agent-bot")
    assert result.account_id == "ACC-001" and result.discount_pct == 10
    assert result.erp_reference.startswith("ERP-")

    with pytest.raises(GrantError, match="already consumed"):
        apply_discount(grant.grant_id, "sales-agent-bot")


def test_expired_grant_is_refused():
    grant = _approved_grant()
    grant.expires_at = utcnow() - timedelta(seconds=1)
    with pytest.raises(GrantError, match="expired"):
        apply_discount(grant.grant_id, "sales-agent-bot")


def test_tampered_evaluation_fails_hash_check():
    grant = _approved_grant()
    request, _ = grant_store.get_evaluation(grant.evaluation_id)
    request.intent.proposed_discount_pct = 50  # mutate after the DMN decided
    with pytest.raises(GrantError, match="hash mismatch"):
        apply_discount(grant.grant_id, "sales-agent-bot")


def test_unknown_grant_is_refused():
    with pytest.raises(GrantError, match="Unknown grant"):
        apply_discount("grant-does-not-exist", "sales-agent-bot")
