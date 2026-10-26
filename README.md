# Fact-Fetching Boundary PoC

Reference implementation for the InfoQ article on the **Fact-Fetching Boundary** pattern:
an LLM agent produces a probabilistic *intent*; a deterministic boundary replaces the agent's
*claims* with *facts* from the System of Record before a DMN model deliberates.

```
AgentIntent ──► Boundary ──► CRM (facts) ──► DMN (Kogito) ──► ExecutionGrant ──► Executor ──► ERP
 (claims)        authz,                         policy           single-use,
                 trigger binding                                  hashed, expiring
```

## Components

| Directory          | What                                                                 | Port |
|--------------------|----------------------------------------------------------------------|------|
| `dmn-service/`     | Spring Boot + Kogito 10.2 serving `discount.dmn` (`DiscountApproval`) | 8080 |
| `crm-api/`         | FastAPI mock CRM (System of Record) with two static customers        | 8000 |
| `boundary_agent/`  | Python: `contracts/models.py`, `boundary/compose.py`, `executor/apply.py`, in-memory mocks in `utils/` | – |
| `tests/`           | Pytest Red/Green scenarios and OpenAPI contract test                 | – |
| `scripts/benchmark.py` | p95 latency, Baseline vs Protected                               | – |

### DMN endpoints (dmn-service)
- `POST /DiscountApproval` – evaluate the model (input = `DiscountApprovalInputSet`)
- `GET /q/openapi.json` – OpenAPI with the DMN schemas inlined (`DiscountApprovalInputSet`, `tFacts`, `tIntent`, …)
- `GET /q/swagger-ui` – Swagger UI
- `GET /actuator/health` – health check

### CRM endpoints (crm-api)
- `GET /resolve_ref/{customer_ref}` – email / name / id → `account_id`
- `GET /facts/{account_id}` – authoritative facts (`tier`, `margin_pct`, `credit_hold`)

Static data: `ACC-001` (alice, standard, margin 20, no hold) and `ACC-002` (bob, premium, margin 18, no hold).

## Run the stack

Prerequisites: Docker with Compose v2. Java 21 + Maven are only needed to build outside Docker.

```bash
docker compose up -d --build        # first build downloads Maven deps, takes a few minutes
docker compose ps                   # wait until both services are "healthy"
```

Smoke test:

```bash
curl -s -X POST localhost:8080/DiscountApproval -H 'Content-Type: application/json' -d '{
  "facts":  {"tier": "standard", "margin_pct": 20.0, "credit_hold": false},
  "intent": {"proposed_discount_pct": 20, "claimed_facts": {"tier": "premium"}}
}'
# → "DiscountApproval": {"Outcome": "REVIEW", "Reason Code": "ESCALATION_EXCEEDS_ENTITLEMENT"}
```

## Run the tests and benchmark

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/                       # 14 tests, needs the stack running
python scripts/benchmark.py         # N=1000 per path, prints p50/p95/p99
```

`DMN_BASE_URL` and `CRM_BASE_URL` override the default `localhost` targets.

### What the suite proves
- **Scenario 1, Baseline (red):** the agent writes `facts.tier = "premium"` itself → DMN returns `APPROVED`.
- **Scenario 1, Protected (green):** same claim through the Boundary → CRM says `standard` → `REVIEW / ESCALATION_EXCEEDS_ENTITLEMENT`, and no grant can be issued.
- **Scenario 2, ID spoofing:** `customer_ref="ACC-002"` while the trigger is bound to `ACC-001` → `TriggerBindingError` before any fact fetch or DMN call.
- **Contract:** `DecisionRequest` (Pydantic, `extra="forbid"`) matches Kogito's `DiscountApprovalInputSet` field-by-field, including types.
- **Executor:** grants are single-use, hash-bound to the evaluated request, timezone-aware and expiring.

## DMN model (`dmn-service/src/main/resources/discount.dmn`)

| Node | Kind | Logic |
|------|------|-------|
| `EntitledMaxDiscount` | decision table | `standard → 10`, `premium → 20` |
| `ClaimEscalation` | literal expression | `intent.claimed_facts.tier = "premium" and facts.tier != "premium"` |
| `DiscountApproval` | decision table, **UNIQUE** | credit hold → `REJECTED/CREDIT_HOLD`; margin `< 15` → `REJECTED/MARGIN_BELOW_FLOOR`; within entitlement → `APPROVED` (`_ESCALATION_LOGGED` if escalated); over entitlement → `REJECTED/EXCEEDS_ENTITLEMENT` or `REVIEW/ESCALATION_EXCEEDS_ENTITLEMENT` if escalated |

## Local development without Docker

```bash
cd dmn-service && mvn package && java -jar target/dmn-service-1.0.0-SNAPSHOT.jar   # runs 7 Java tests too
cd crm-api && pip install -r requirements.txt && uvicorn main:app --port 8000
```

## Notes
- The PRD names Quarkus; this implementation uses **Spring Boot** with the same Kogito engine. Everything observable is preserved (`/DiscountApproval`, `/q/openapi.json`, ports). Only the health path differs (`/actuator/health` instead of `/q/health`).
- On Spring Boot, Kogito publishes the DMN schemas as an external `/refs/discount.json`; `DmnOpenApiCustomizer.java` inlines them into the OpenAPI document under the Quarkus names so the contract test works as specified.
