"""
Generation evaluation — RAGAS-style faithfulness and answer relevancy.

Uses llama-3.1-8b-instant (via Groq) as an LLM judge for two metrics:

  Faithfulness:     fraction of plan claims traceable to retrieved context.
  Answer Relevancy: how well the plan addresses the stated user profile.

Also measures end-to-end latency (retrieval + Groq generation) p50/p95.

Reads: backend/eval/eval_set.json  (uses first EVAL_SAMPLE queries)
Appends: backend/eval/results.md

Usage (from backend/):
    python -m eval.run_generation_eval [--sample N]
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

from groq import Groq

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
RESULTS_PATH  = Path(__file__).parent / "results.md"

JUDGE_MODEL = "llama-3.1-8b-instant"
DEFAULT_SAMPLE = 12   # keep costs minimal


# ---------------------------------------------------------------------------
# Judge prompts
# ---------------------------------------------------------------------------

_FAITH_SYSTEM = (
    "You are a strict evidence evaluator. Respond with raw JSON only — "
    "no markdown fences, no commentary."
)

_FAITH_USER = """\
Context passages retrieved from a fitness knowledge base:
{context}

Training plan summary and general tips:
{plan_text}

On a scale 0.0-1.0, what fraction of the specific training recommendations in
the plan are directly supported by the context passages above? A claim is
supported only if it can be traced to specific wording or data in the context.
Generic advice (e.g. "warm up before exercising") counts only if the context
explicitly mentions it.

Output JSON: {{"score": <float 0-1>, "reasoning": "<one sentence>"}}
"""

_RELEV_SYSTEM = (
    "You are a fitness plan quality evaluator. Respond with raw JSON only — "
    "no markdown fences, no commentary."
)

_RELEV_USER = """\
User profile:
  Goal: {goal}
  Fitness level: {level}
  Available equipment: {equipment}

Plan title: {title}
Plan summary: {summary}

On a scale 0.0-1.0, how relevant is this plan to the stated user profile?
Consider:
  - Goal alignment (does the plan address the stated goal?)
  - Fitness level appropriateness (is complexity right for the level?)
  - Equipment specificity (does it stick to what's available?)

Output JSON: {{"score": <float 0-1>, "reasoning": "<one sentence>"}}
"""


# ---------------------------------------------------------------------------
# Judge helpers
# ---------------------------------------------------------------------------

def _parse_judge_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def score_faithfulness(context: str, plan_text: str, client: Groq) -> dict:
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": _FAITH_SYSTEM},
            {"role": "user",   "content": _FAITH_USER.format(
                context=context[:3000], plan_text=plan_text[:1500],
            )},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    return _parse_judge_response(resp.choices[0].message.content)


def score_relevancy(goal: str, level: str, equipment: str,
                    title: str, summary: str, client: Groq) -> dict:
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": _RELEV_SYSTEM},
            {"role": "user",   "content": _RELEV_USER.format(
                goal=goal, level=level, equipment=equipment,
                title=title, summary=summary,
            )},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    return _parse_judge_response(resp.choices[0].message.content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_onboarding(ctx: dict):
    from app.schemas.workout import (
        OnboardingData, FitnessGoal, FitnessLevel, Equipment,
    )
    return OnboardingData(
        name="EvalUser",
        age=25,
        fitness_goal=FitnessGoal(ctx["fitness_goal"]),
        fitness_level=FitnessLevel(ctx["fitness_level"]),
        available_equipment=[Equipment(e) for e in ctx["available_equipment"]],
        days_per_week=3,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run(sample: int) -> None:
    from app.database import SessionLocal
    from app.services.retrieval_service import retrieve, _get_embed_model, _get_reranker
    from app.services.ai_service import generate_workout_plan, _build_retrieval_query

    print("Pre-loading models …")
    _get_embed_model()
    _get_reranker()
    print("Models ready.\n")

    groq_key = os.environ.get("GROQ_API_KEY") or ""
    if not groq_key:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GROQ_API_KEY="):
                    groq_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not groq_key:
        print("ERROR: GROQ_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    judge = Groq(api_key=groq_key)

    eval_set   = json.loads(EVAL_SET_PATH.read_text())
    eval_sample = eval_set[:sample]

    print(f"Evaluating {len(eval_sample)} queries (of {len(eval_set)} total)\n")

    records = []

    db = SessionLocal()
    try:
        for i, q in enumerate(eval_sample, 1):
            ctx = q["onboarding_context"]
            onboarding = _make_onboarding(ctx)

            print(f"  [{i}/{len(eval_sample)}] {q['query_id']}: {q['query'][:60]}")

            # ── Retrieve context (mirrors what generate_workout_plan does) ──
            retrieval_q = _build_retrieval_query(onboarding)
            try:
                rr = retrieve(retrieval_q, onboarding, k=5, db=db)
                context_text = "\n\n".join(c.raw_content for c in rr.chunks)
            except Exception as exc:
                print(f"    WARN retrieval: {exc}")
                context_text = ""

            # ── Generate plan ────────────────────────────────────────────────
            t0 = time.perf_counter()
            try:
                plan = await generate_workout_plan(onboarding, db=db)
                latency_s = time.perf_counter() - t0
            except Exception as exc:
                print(f"    WARN generation: {exc}")
                records.append({
                    "query_id": q["query_id"],
                    "error": str(exc),
                })
                continue

            plan_text = f"Title: {plan.title}\nSummary: {plan.summary}\nTips: {' '.join(plan.general_tips)}"

            # ── Judge faithfulness ───────────────────────────────────────────
            faith_result, relev_result = {}, {}
            try:
                faith_result = score_faithfulness(context_text, plan_text, judge)
                print(f"    faithfulness={faith_result.get('score', '?'):.2f}  {faith_result.get('reasoning', '')[:60]}")
            except Exception as exc:
                print(f"    WARN faithfulness: {exc}")

            # ── Judge relevancy ──────────────────────────────────────────────
            try:
                eq_str = ", ".join(ctx["available_equipment"])
                relev_result = score_relevancy(
                    ctx["fitness_goal"], ctx["fitness_level"], eq_str,
                    plan.title, plan.summary, judge,
                )
                print(f"    relevancy   ={relev_result.get('score', '?'):.2f}  {relev_result.get('reasoning', '')[:60]}")
            except Exception as exc:
                print(f"    WARN relevancy: {exc}")

            records.append({
                "query_id":            q["query_id"],
                "grounded":            plan.grounded,
                "faithfulness_score":  faith_result.get("score"),
                "faithfulness_reason": faith_result.get("reasoning", ""),
                "relevancy_score":     relev_result.get("score"),
                "relevancy_reason":    relev_result.get("reasoning", ""),
                "latency_s":           latency_s,
            })

            time.sleep(0.5)   # Groq rate-limit headroom
    finally:
        db.close()

    # ── Aggregate ────────────────────────────────────────────────────────────

    faith_scores = [r["faithfulness_score"] for r in records if r.get("faithfulness_score") is not None]
    relev_scores = [r["relevancy_score"]    for r in records if r.get("relevancy_score")    is not None]
    latencies    = sorted(r["latency_s"]    for r in records if r.get("latency_s")          is not None)

    mean_faith = statistics.mean(faith_scores) if faith_scores else float("nan")
    std_faith  = statistics.stdev(faith_scores) if len(faith_scores) > 1 else 0.0
    mean_relev = statistics.mean(relev_scores) if relev_scores else float("nan")
    std_relev  = statistics.stdev(relev_scores) if len(relev_scores) > 1 else 0.0
    p50_lat    = statistics.median(latencies) if latencies else float("nan")
    p95_lat    = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else float("nan")

    print(f"\nFaithfulness:   {mean_faith:.3f} ± {std_faith:.3f}")
    print(f"Answer Relevancy: {mean_relev:.3f} ± {std_relev:.3f}")
    print(f"E2E Latency:    p50={p50_lat:.1f}s  p95={p95_lat:.1f}s")

    # ── Build markdown section ───────────────────────────────────────────────

    per_query_rows = ""
    for r in records:
        if "error" in r:
            per_query_rows += f"| {r['query_id']} | ERROR | — | — | — |\n"
        else:
            g = "✓" if r.get("grounded") else "✗"
            per_query_rows += (
                f"| {r['query_id']} | {g} "
                f"| {r.get('faithfulness_score', 0):.2f} "
                f"| {r.get('relevancy_score', 0):.2f} "
                f"| {r.get('latency_s', 0):.1f}s |\n"
            )

    gen_section = f"""## Generation Evaluation (RAGAS-style)

**Dataset**: {len(eval_sample)}-query subsample of eval_set.json
**Judge model**: {JUDGE_MODEL}
**Metrics**: Faithfulness (plan claims grounded in retrieved context), Answer Relevancy (profile fit)

| Metric | Score |
|--------|-------|
| Faithfulness (mean ± std) | {mean_faith:.3f} ± {std_faith:.3f} |
| Answer Relevancy (mean ± std) | {mean_relev:.3f} ± {std_relev:.3f} |
| E2E Latency p50 | {p50_lat:.2f}s |
| E2E Latency p95 | {p95_lat:.2f}s |

### Per-query breakdown

| query_id | grounded | faithfulness | relevancy | latency |
|----------|----------|--------------|-----------|---------|
{per_query_rows}
**Note**: Faithfulness scores are relative, not absolute — the LLM judge is not
calibrated. Numbers above 0.7 indicate strong context grounding; below 0.4
suggests the model is drawing on parametric knowledge beyond the retrieved chunks.
"""

    # Append to results.md
    if RESULTS_PATH.exists():
        existing = RESULTS_PATH.read_text()
        marker = "\n## Generation Evaluation"
        if marker in existing:
            existing = existing[: existing.index(marker)]
        RESULTS_PATH.write_text(existing.rstrip() + "\n\n---\n\n" + gen_section)
    else:
        RESULTS_PATH.write_text(
            "# FitForge RAG — Evaluation Results\n\n---\n\n" + gen_section
        )

    print(f"\nGeneration results appended to {RESULTS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE,
                        help=f"Number of eval queries to use (default: {DEFAULT_SAMPLE})")
    args = parser.parse_args()
    asyncio.run(_run(args.sample))


if __name__ == "__main__":
    main()
