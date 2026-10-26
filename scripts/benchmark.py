"""Latency benchmark: Baseline (direct DMN call) vs Protected (Boundary -> CRM -> DMN).

Usage: python scripts/benchmark.py [N]   (default N=1000)
"""

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boundary_agent.boundary import compose  # noqa: E402
from boundary_agent.contracts.models import AgentIntent, ClaimedFacts, TriggerContext  # noqa: E402
from boundary_agent.utils import clients, grant_store  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
WARMUP = 50

BASELINE_PAYLOAD = {
    "facts": {"tier": "premium", "margin_pct": 20.0, "credit_hold": False},
    "intent": {"proposed_discount_pct": 20, "claimed_facts": {"tier": "premium"}},
}
INTENT = AgentIntent(customer_ref="alice@example.com", proposed_discount_pct=20,
                     claimed_facts=ClaimedFacts(tier="premium"))
TRIGGER = TriggerContext(account_id="ACC-001", actor_id="sales-agent-bot")


def baseline() -> None:
    clients.evaluate_raw(BASELINE_PAYLOAD)


def protected() -> None:
    compose.run_protected(INTENT, TRIGGER)


def run(name, fn):
    for _ in range(WARMUP):
        fn()
    samples = []
    for _ in range(N):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
        if len(grant_store._EVALUATIONS) > 200:
            grant_store.clear()
    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[int(round(0.95 * (N - 1)))]
    p99 = samples[int(round(0.99 * (N - 1)))]
    return name, p50, p95, p99, statistics.mean(samples)


if __name__ == "__main__":
    print(f"N={N} iterations per path (+{WARMUP} warm-up), sequential, single client\n")
    rows = [run("Baseline  (direct DMN)", baseline), run("Protected (Boundary->CRM->DMN)", protected)]
    print(f"{'path':34} {'p50 ms':>9} {'p95 ms':>9} {'p99 ms':>9} {'mean ms':>9}")
    for name, p50, p95, p99, mean in rows:
        print(f"{name:34} {p50:9.2f} {p95:9.2f} {p99:9.2f} {mean:9.2f}")
    overhead = rows[1][2] - rows[0][2]
    print(f"\nBoundary p95 overhead: +{overhead:.2f} ms ({rows[1][2] / rows[0][2]:.2f}x)")
