"""In-memory authorization mock: who may perform which action on which account."""

_POLICY: dict[str, dict[str, set[str]]] = {
    # actor_id -> action -> allowed account_ids ("*" = any)
    "sales-agent-bot": {"propose_discount": {"*"}, "apply_discount": {"*"}},
    "support-agent-bot": {"propose_discount": {"ACC-001"}},
}


def can_act(actor_id: str, action: str, account_id: str) -> bool:
    allowed = _POLICY.get(actor_id, {}).get(action, set())
    return "*" in allowed or account_id in allowed
