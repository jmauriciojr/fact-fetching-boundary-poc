"""Executor: the only component allowed to touch the ERP, and only with a valid grant."""

from __future__ import annotations

from boundary_agent.contracts.models import ExecutionResult, GrantError, Outcome, utcnow
from boundary_agent.utils import authz, erp, grant_store
from boundary_agent.utils.crypto import canonical_hash


def apply_discount(grant_id: str, actor_id: str) -> ExecutionResult:
    # 1. The grant must exist and be unused.
    grant = grant_store.get_grant(grant_id)
    if grant is None:
        raise GrantError(f"Unknown grant {grant_id}")
    if grant.consumed:
        raise GrantError(f"Grant {grant_id} already consumed")

    # 2. The evaluation it points to must exist and be APPROVED.
    stored = grant_store.get_evaluation(grant.evaluation_id)
    if stored is None:
        raise GrantError(f"Grant {grant_id} references unknown evaluation {grant.evaluation_id}")
    request, response = stored
    if response.outcome is not Outcome.APPROVED:
        raise GrantError(f"Evaluation {grant.evaluation_id} is {response.outcome.value}, not APPROVED")

    # 3. Integrity: the request the DMN saw must hash to what the grant carries.
    if canonical_hash(request.model_dump(mode="json")) != grant.request_hash or grant.request_hash != response.request_hash:
        raise GrantError(f"Grant {grant_id} hash mismatch (request tampered after evaluation)")

    # 4. Freshness and consistency.
    if utcnow() >= grant.expires_at:
        raise GrantError(f"Grant {grant_id} expired at {grant.expires_at.isoformat()}")
    if grant.discount_pct != request.intent.proposed_discount_pct:
        raise GrantError(f"Grant {grant_id} discount does not match evaluated request")

    # 5. Authorization for the execution action itself.
    if not authz.can_act(actor_id, "apply_discount", grant.account_id):
        raise GrantError(f"{actor_id} may not apply discounts for {grant.account_id}")

    # 6. Side effect, then burn the grant.
    ref = erp.apply_discount(grant.account_id, grant.discount_pct, grant.grant_id)
    grant.consumed = True
    return ExecutionResult(
        grant_id=grant.grant_id,
        evaluation_id=grant.evaluation_id,
        account_id=grant.account_id,
        discount_pct=grant.discount_pct,
        erp_reference=ref,
    )
