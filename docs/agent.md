# Agent — self-reflection critique loop

Moved out of the README to keep the front page short.

**Status:** this endpoint (`POST /api/workout/generate-agent`) is implemented and
unit-tested, but the web app does not call it — the UI uses the single-pass
`POST /api/workout/generate`. Treat it as a backend capability, not part of the
shipped user flow.

## How it works

`POST /api/workout/generate-agent` wraps the RAG pipeline in a LangGraph
state machine that scores every generated plan and rewrites it if it falls
short. The existing `/generate` endpoint is unchanged.

### Graph shape

```
retrieve → generate → critique ──accepted──► return best plan
                          └──rejected, budget left──► refine ──► critique (repeat)
```

Each node is a discrete step in the state machine:

| Node | Model | What it does |
|------|-------|-------------|
| `retrieve` | — | RAG lookup (hybrid dense + sparse + RRF); sets `generation_mode` |
| `generate` | 70B | Produces the initial JSON workout plan |
| `critique` | 8B | Scores the plan 0–1 and lists constraint violations |
| `refine` | 70B | Rewrites the plan with critic feedback prepended to context |

The **highest-scoring plan seen across all iterations** is returned, not the
last one. If the critic improves the plan in iteration 1 but then a parse
error causes iteration 2 to fail open, the iteration-1 plan is still
returned.

### Why a separate endpoint?

`/generate` is in production, has a stable contract, and its behaviour must
not change for existing frontend clients. The agent adds latency (see cost
below), changes the generation path, and is still being evaluated. A separate
endpoint lets both co-exist and lets the eval harness compare them directly
on identical inputs.

### What the critic validates — and what it does not

**Validates (profile constraint alignment):**
- **equipment** — does the plan use equipment the user does not have?
- **goal** — does the plan structure match the stated fitness goal?
- **level** — is the intensity appropriate for the user's experience level?
- **completeness** — is the plan sufficient for the number of training days?

**Does not validate:**
- **Factual grounding** — the critic never sees the retrieved KB chunks.
  It cannot tell whether a claim like "4 sets of 8–12 reps" is supported by
  the cited ACSM guidelines. Factual accuracy is the retrieval pipeline's job;
  the critic only checks profile constraint alignment.

Keep these two separate when describing the system. The critic is not a
fact-checker.

### Acceptance is computed in Python, not by the model

The critic LLM returns a numeric `score` and a list of structured issues
(each with a `category` field constrained to `{"goal", "equipment", "level",
"completeness"}`). The `accepted` decision is computed in Python:

```python
equipment_violation = any(i["category"] == "equipment" for i in issues)
accepted = (score >= AGENT_CRITIQUE_THRESHOLD) and not equipment_violation
```

The model is never asked to decide its own score or whether the plan should
be accepted. This prevents the model from soft-pedalling a clear equipment
violation by writing `"accepted": true` despite flagging it. It also makes
the acceptance logic auditable and testable without LLM calls.

### Configuration

| Env variable | Default | Meaning |
|---|---|---|
| `AGENT_MAX_ITERATIONS` | `2` | Maximum refine cycles. `0` = generate + critique only, no refinement. |
| `AGENT_CRITIQUE_THRESHOLD` | `0.75` | Score threshold for acceptance. Equipment violations block acceptance regardless of score. |

### Worst-case LLM cost

With `AGENT_MAX_ITERATIONS=2`, a plan that fails both critiques makes:
- 1 × **generate** (70B)
- 2 × **refine** (70B)
- 3 × **critique** (8B)

= **6 LLM calls total**. Wall-clock latency is logged per request
(`run_agent complete: ... elapsed_ms=...`).

### Eval results

<!-- PLACEHOLDER — fill in after running `python -m scripts.eval_agent` -->

| Metric | Value |
|---|---|
| Profiles | — |
| Critic rejection rate (1st critique) | — |
| Adversarial rejection rate | — |
| Equipment violations | — |
| Parse-error rate | — |
| Runs that entered refine | — |
| Refine improved best_score | — |
| `/generate` p50 latency | — |
| `/generate-agent` p50 latency | — |
| Latency delta (p50) | — |

_Run `python -m scripts.eval_agent --email <email> --password <pw> --log-file backend.log`
from `backend/` to populate this table._

---
