"""The Fact-Fetching Boundary.

Order of operations is the whole point:
  1. authorization        -> can this actor act on this account at all?
  2. trigger binding      -> does the agent's customer_ref resolve to the *triggering* account?
  3. fact fetching        -> facts come from the System of Record, never from the agent
  4. composition          -> strict DecisionRequest (extra keys forbidden)
Then ``evaluate`` sends it to the DMN and ``issue_grant`` turns an APPROVED outcome into a grant.
"""

from __future__ import annotations

from datetime import timedelta

from boundary_agent import config
from boundary_agent.contracts.models import (
    AgentIntent,
    AuthorizationError,
    DecisionRequest,
    DecisionResponse,
    ExecutionGrant,
    GrantError,
    IntentInput,
    Outcome,
    TriggerBindingError,
    TriggerContext,
    utcnow,
)
from boundary_agent.utils import authz, clients, grant_store
from boundary_agent.utils.crypto import canonical_hash


def compose_decision_request(intent: AgentIntent, trigger: TriggerContext) -> DecisionRequest:
    # 1. Authorization
    if not authz.can_act(trigger.actor_id, "propose_discount", trigger.account_id):
        raise AuthorizationError(f"{trigger.actor_id} may not propose discounts for {trigger.account_id}")

    # 2. Trigger binding: resolve the agent-supplied reference and pin it to the trigger.
    resolved_account_id = clients.resolve_ref(intent.customer_ref)
    if resolved_account_id != trigger.account_id:
        raise TriggerBindingError(
            f"customer_ref {intent.customer_ref!r} resolves to {resolved_account_id}, "
            f"but the trigger is bound to {trigger.account_id}"
        )

    # 3. Fact fetching from the System of Record (only after binding succeeded).
    facts = clients.fetch_facts(trigger.account_id)

    # 4. Composition. claimed_facts travel as *intent*, never as *facts*.
    return DecisionRequest(
        facts=facts,
        intent=IntentInput(
            proposed_discount_pct=intent.proposed_discount_pct,
            claimed_facts=intent.claimed_facts,
        ),
    )


def evaluate(request: DecisionRequest) -> DecisionResponse:
    payload = request.model_dump(mode="json")
    raw = clients.evaluate_raw(payload)
    result = raw["DiscountApproval"]
    response = DecisionResponse(
        outcome=Outcome(result["Outcome"]),
        reason_code=result["Reason Code"],
        entitled_max_discount=float(raw["EntitledMaxDiscount"]),
        claim_escalation=bool(raw["ClaimEscalation"]),
        request_hash=canonical_hash(payload),
        raw=raw,
    )
    grant_store.save_evaluation(request, response)
    return response


def issue_grant(response: DecisionResponse, trigger: TriggerContext) -> ExecutionGrant:
    if response.outcome is not Outcome.APPROVED:
        raise GrantError(f"Cannot issue grant for outcome {response.outcome.value} ({response.reason_code})")
    stored = grant_store.get_evaluation(response.evaluation_id)
    if stored is None:
        raise GrantError(f"Unknown evaluation {response.evaluation_id}")
    request, _ = stored
    grant = ExecutionGrant(
        evaluation_id=response.evaluation_id,
        account_id=trigger.account_id,
        discount_pct=request.intent.proposed_discount_pct,
        request_hash=response.request_hash,
        expires_at=utcnow() + timedelta(seconds=config.GRANT_TTL_SECONDS),
    )
    grant_store.save_grant(grant)
    return grant


def run_protected(intent: AgentIntent, trigger: TriggerContext) -> DecisionResponse:
    """Full Protected path: boundary -> CRM -> DMN."""
    return evaluate(compose_decision_request(intent, trigger))
