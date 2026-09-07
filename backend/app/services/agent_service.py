"""
LangGraph self-reflection + refinement agent for workout plan generation.

Public API:
    run_agent(data, session_history=None, db=None) -> WorkoutPlan

The agent runs a critique loop on top of the existing RAG pipeline:

    retrieve → generate → critique ──accepted──► return best plan
                               └──rejected, budget left──► refine ──► critique

The highest-scoring plan seen across all iterations is returned, not the last.
LLM calls: 1 generate + up to agent_max_iterations×(1 refine + 1 critique).

NOTE: AgentState holds a live SQLAlchemy Session in the `db` field.
Sessions are not serialisable, so this graph cannot use a LangGraph
checkpointer without injecting db via RunnableConfig instead.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional, TypedDict

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.workout import OnboardingData, WorkoutPlan
from app.services.ai_service import (
    _LOW_CONFIDENCE_BLOCK,
    _build_context_block,
    _build_retrieval_query,
    _build_system_prompt,
    _build_user_prompt,
    _get_client,
)
from app.services.retrieval_service import retrieve

log = logging.getLogger(__name__)

VALID_CATEGORIES = {"goal", "equipment", "level", "completeness"}


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    onboarding_data: Any           # OnboardingData instance
    session_history: Optional[str]
    db: Any                        # SQLAlchemy Session (not serialisable)
    generation_mode: str           # "grounded" | "low_confidence" | "no_retrieval"
    context_block: Optional[str]   # numbered KB block, low-confidence note, or None
    plan_dict: Optional[dict]      # current plan (overwritten by refine_node)
    best_plan_dict: Optional[dict] # highest-scored plan seen across all iterations
    best_score: float              # critic score for best_plan_dict (0.0 initially)
    critique: Optional[dict]       # {score, issues, accepted, equipment_violation}
    iteration: int                 # refine cycles completed (incremented in refine_node)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def retrieve_node(state: AgentState) -> dict:
    """Run RAG retrieval and set generation_mode + context_block in state.

    Guards db=None so the no_retrieval path is taken rather than crashing.
    """
    if state["db"] is None:
        return {"generation_mode": "no_retrieval", "context_block": None}
    query = _build_retrieval_query(state["onboarding_data"])
    result = retrieve(query, state["onboarding_data"], k=5, db=state["db"])
    if result.low_confidence:
        return {"generation_mode": "low_confidence", "context_block": _LOW_CONFIDENCE_BLOCK}
    return {
        "generation_mode": "grounded",
        "context_block": _build_context_block(result.chunks),
    }


async def generate_node(state: AgentState) -> dict:
    """Call Groq to produce the initial workout plan JSON."""
    completion = _get_client().chat.completions.create(
        model=settings.groq_model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _build_system_prompt(state["generation_mode"])},
            {
                "role": "user",
                "content": _build_user_prompt(
                    state["onboarding_data"],
                    state["session_history"],
                    state["context_block"],
                ),
            },
        ],
    )
    raw = completion.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    plan_dict = json.loads(raw)
    return {"plan_dict": plan_dict}


async def critique_node(state: AgentState) -> dict:
    """Score the current plan with a lightweight 8b critic.

    Returns accepted=True on JSON parse failure (fail-open) and emits a
    structured log.info line in both paths so parse failures count in the
    rejection-rate denominator.
    """
    t0 = time.perf_counter()
    plan = state["plan_dict"]
    od = state["onboarding_data"]

    goal = od.fitness_goal.value.replace("_", " ")
    level = od.fitness_level.value
    equipment = ", ".join(e.value.replace("_", " ") for e in od.available_equipment)
    days = od.days_per_week

    exercise_lines: list[str] = []
    for day in plan.get("days", []):
        for ex in day.get("exercises", []):
            exercise_lines.append(f"{ex.get('name')} | {ex.get('sets')}×{ex.get('reps')}")
            if len(exercise_lines) >= 20:
                break
        if len(exercise_lines) >= 20:
            break

    user_content = (
        f"Profile: goal={goal}, level={level}, equipment={equipment}, days={days}\n\n"
        f"Plan title: {plan.get('title')}\n"
        f"Plan summary: {plan.get('summary')}\n"
        "Exercises (first 20 only — violations past index 20 are not evaluated):\n"
        + "\n".join(exercise_lines)
        + "\n\nScore this plan 0.0–1.0 on four dimensions and report each violation.\n"
        'category MUST be one of: "goal" | "equipment" | "level" | "completeness"\n\n'
        "Output:\n"
        '{\n  "score": <float 0-1>,\n'
        '  "issues": [\n'
        '    {"category": "equipment", "detail": "Barbell required but only dumbbells listed"}\n'
        "  ]\n}"
    )

    completion = _get_client().chat.completions.create(
        model=settings.groq_context_model,
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": "You are a fitness plan quality auditor. Respond with raw JSON only — no fences.",
            },
            {"role": "user", "content": user_content},
        ],
    )
    raw = completion.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw)
        score = float(parsed["score"])
        raw_issues = parsed.get("issues", [])
        # Drop issues with unknown categories to prevent prompt-injection or model drift
        issues = [i for i in raw_issues if i.get("category") in VALID_CATEGORIES]
        parse_error = False
    except (json.JSONDecodeError, ValueError, KeyError):
        score, issues, parse_error = 0.0, [], True

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if parse_error:
        log.info(
            "agent_critique iter=%d score=0.000 accepted=True equip_violation=False "
            "parse_error=1 elapsed_ms=%d",
            state["iteration"],
            elapsed_ms,
        )
        return {
            "critique": {
                "score": 0.0,
                "issues": [],
                "accepted": True,
                "equipment_violation": False,
                "parse_error": True,
            }
        }

    # accepted is Python-computed — never delegated to the LLM
    equipment_violation = any(i.get("category") == "equipment" for i in issues)
    accepted = (score >= settings.agent_critique_threshold) and not equipment_violation

    critique = {
        "score": score,
        "issues": issues,
        "accepted": accepted,
        "equipment_violation": equipment_violation,
    }

    log.info(
        "agent_critique iter=%d score=%.3f accepted=%s equip_violation=%s "
        "issue_categories=%s elapsed_ms=%d",
        state["iteration"],
        score,
        accepted,
        equipment_violation,
        [i["category"] for i in issues],
        elapsed_ms,
    )

    updates: dict = {"critique": critique}
    if score > state.get("best_score", 0.0):
        updates["best_plan_dict"] = state["plan_dict"]
        updates["best_score"] = score

    return updates


async def refine_node(state: AgentState) -> dict:
    """Rewrite the plan with critic feedback prepended to the context.

    Increments iteration here (not in critique_node) so the budget check
    in route_after_critique reflects completed refine cycles, not critique calls.
    """
    issues = state["critique"].get("issues", [])
    feedback_lines = "\n".join(f"- {i.get('detail', '')}" for i in issues)
    feedback_block = (
        f"[CRITIC FEEDBACK — you MUST address every issue listed]\n"
        f"Issues from quality review (iteration {state['iteration']}):\n"
        f"{feedback_lines}"
    )

    combined_context = (
        feedback_block + "\n\n" + state["context_block"]
        if state["context_block"]
        else feedback_block
    )

    completion = _get_client().chat.completions.create(
        model=settings.groq_model,
        max_tokens=4096,
        messages=[
            {
                "role": "system",
                "content": _build_system_prompt(state["generation_mode"]),
            },
            {
                "role": "user",
                "content": _build_user_prompt(
                    state["onboarding_data"],
                    state["session_history"],
                    combined_context,
                ),
            },
        ],
    )
    raw = completion.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    revised_plan_dict = json.loads(raw)
    return {"plan_dict": revised_plan_dict, "iteration": state["iteration"] + 1}


# ---------------------------------------------------------------------------
# Routing edge
# ---------------------------------------------------------------------------

def route_after_critique(state: AgentState) -> str:
    if (
        not state["critique"]["accepted"]
        and state["iteration"] < settings.agent_max_iterations
    ):
        return "refine"
    return "__end__"


# ---------------------------------------------------------------------------
# Graph compilation (extracted for testability)
# ---------------------------------------------------------------------------

def _build_graph():
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(AgentState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    # Node name deliberately differs from the "critique" state key it writes.
    # LangGraph rejects a node whose name collides with a state key
    # (ValueError: 'critique' is already being used as a state key), which is
    # what broke graph construction — and with it every test in this module —
    # once the unpinned langgraph dependency moved past 0.2.
    workflow.add_node("critique_plan", critique_node)
    workflow.add_node("refine", refine_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "critique_plan")
    workflow.add_conditional_edges(
        "critique_plan",
        route_after_critique,
        {"refine": "refine", "__end__": END},
    )
    workflow.add_edge("refine", "critique_plan")

    return workflow.compile()


agent_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_agent(
    data: OnboardingData,
    session_history: Optional[str] = None,
    db: Optional[Session] = None,
) -> WorkoutPlan:
    """Run the self-reflection agent and return the highest-scored plan."""
    t0 = time.perf_counter()
    initial_state: AgentState = {
        "onboarding_data": data,
        "session_history": session_history,
        "db": db,
        "generation_mode": "no_retrieval",
        "context_block": None,
        "plan_dict": None,
        "best_plan_dict": None,
        "best_score": 0.0,
        "critique": None,
        "iteration": 0,
    }
    final_state = await agent_graph.ainvoke(initial_state)

    log.info(
        "run_agent complete: total_refine_cycles=%d best_score=%.3f elapsed_ms=%d",
        final_state["iteration"],
        final_state["best_score"],
        int((time.perf_counter() - t0) * 1000),
    )

    # best_plan_dict is set by critique_node whenever score improves.
    # Fall back to plan_dict only if no critique ever ran (e.g. all nodes errored).
    plan_dict = final_state["best_plan_dict"] or final_state["plan_dict"]

    # Server-side grounded/citations override — same authority as generate_workout_plan
    gen_mode = final_state["generation_mode"]
    if gen_mode == "grounded":
        plan_dict["grounded"] = True
    elif gen_mode == "low_confidence":
        plan_dict["grounded"] = False
        plan_dict["citations"] = []
    else:  # "no_retrieval"
        plan_dict["grounded"] = True
        plan_dict["citations"] = []

    return WorkoutPlan(**plan_dict)
