"""
Groq API service for AI workout plan generation.

Responsible for:
  1. Retrieving relevant knowledge base chunks (RAG — Phase 3)
  2. Building a grounded prompt with [N]-labelled context passages
  3. Calling the Groq API (OpenAI-compatible chat completions)
  4. Parsing the JSON response into WorkoutPlan schema objects
  5. Overriding `grounded` server-side from the retrieval confidence signal

Separation of concerns: the router calls this service; the service owns
all AI-specific logic so it can be swapped or tested independently.
"""

import json
import logging
from typing import Optional

from groq import Groq, APIError
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.workout import OnboardingData, WorkoutPlan

logger = logging.getLogger(__name__)

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


# ── Retrieval query ────────────────────────────────────────────────────────────

def _build_retrieval_query(data: OnboardingData) -> str:
    """Construct a fitness-relevant retrieval query from onboarding fields."""
    goal = data.fitness_goal.value.replace("_", " ")
    level = data.fitness_level.value
    equipment = ", ".join(e.value.replace("_", " ") for e in data.available_equipment[:2])
    return f"{goal} training program for {level} with {equipment}"


# ── Context block ──────────────────────────────────────────────────────────────

def _build_context_block(chunks) -> str:
    """Format retrieved chunks as a numbered reference block for the prompt.

    Uses raw_content (not contextualized_content) — the contextualisation
    blurb was added to help the embedding model; the LLM should see the
    original prose so its citations map to real source text.
    """
    lines = ["[KNOWLEDGE BASE CONTEXT — cite as [N] where relevant]\n"]
    for i, chunk in enumerate(chunks, start=1):
        lines.append(f"[{i}] {chunk.raw_content}\n")
    return "\n".join(lines)


_LOW_CONFIDENCE_BLOCK = (
    "[KNOWLEDGE BASE NOTE: No high-confidence reference material was found for "
    "this user profile. Provide conservative, evidence-based general advice. "
    "Set 'grounded' to false in your response and set 'citations' to []. "
    "Mention in the summary that this plan is based on general fitness principles.]"
)


# ── Prompt builders ────────────────────────────────────────────────────────────

def _build_system_prompt(generation_mode: str) -> str:
    """Build the system prompt for three structurally distinct generation paths.

    generation_mode values:
      "grounded"       — retrieval ran and returned high-confidence chunks;
                         instruct the model to cite and set grounded=true.
      "low_confidence" — retrieval ran but returned nothing useful;
                         instruct the model to set grounded=false, citations=[].
      "no_retrieval"   — db=None, pre-RAG compatibility path;
                         no retrieval signal exists, no grounded/citation
                         instructions sent — schema defaults apply server-side.
    """
    base = (
        "You are FitForge AI, an expert personal trainer and sports scientist. "
        "Your task is to create personalised, safe, and effective weekly workout plans. "
        "Always return valid JSON that matches the schema described in the user message. "
        "Do NOT include markdown code fences — return raw JSON only."
    )
    if generation_mode == "grounded":
        return base + (
            " When making specific training recommendations, cite the relevant "
            "knowledge base entries as [1], [2], etc. List each citation used in "
            "the 'citations' array as a short phrase, e.g. '[1] ACSM volume guidelines'. "
            "Set 'grounded' to true."
        )
    if generation_mode == "low_confidence":
        return base + " Set 'citations' to [] and 'grounded' to false."
    # "no_retrieval" — base only; grounded/citations not mentioned, schema defaults apply
    return base


def _build_user_prompt(
    data: OnboardingData,
    session_history: Optional[str],
    context_block: Optional[str],
) -> str:
    equipment_str = ", ".join(e.value.replace("_", " ") for e in data.available_equipment)
    goal_str = data.fitness_goal.value.replace("_", " ")
    level_str = data.fitness_level.value

    context_section = f"\n{context_block}\n" if context_block else ""

    prompt = f"""{context_section}
Create a personalised {data.days_per_week}-day weekly workout plan for:

- Name: {data.name}
- Age: {data.age}
- Fitness goal: {goal_str}
- Fitness level: {level_str}
- Available equipment: {equipment_str}
- Training days per week: {data.days_per_week}
{"- Additional notes: " + data.additional_notes if data.additional_notes else ""}
{"- User's recent training data: " + session_history + ". Based on this, adjust exercise selection and difficulty accordingly." if session_history else ""}

Return ONLY a JSON object with this exact structure (no extra keys, no markdown):

{{
  "title": "<short descriptive plan title>",
  "summary": "<2-3 sentence overview of the plan and why it suits this person>",
  "generated_for": "{data.name}",
  "citations": ["[1] <short phrase describing what chunk 1 supports>", "..."],
  "grounded": true,
  "general_tips": [
    "<tip 1 about nutrition, recovery, or progression>",
    "<tip 2>",
    "<tip 3>"
  ],
  "days": [
    {{
      "day": "Day 1",
      "focus": "<muscle group or training style>",
      "duration_minutes": <integer>,
      "warmup_notes": "<brief warmup description>",
      "cooldown_notes": "<brief cooldown description>",
      "exercises": [
        {{
          "name": "<exercise name>",
          "sets": <integer or null>,
          "reps": "<e.g. '8-12' or '45 seconds' or null>",
          "rest_seconds": <integer or null>,
          "notes": "<form tip or modification>"
        }}
      ]
    }}
  ]
}}

Include {data.days_per_week} training days. Rest days should NOT be included as separate entries.
Make sure exercises are appropriate for {level_str} level and use ONLY the listed equipment.
"""
    return prompt.strip()


# ── Main generation function ───────────────────────────────────────────────────

async def generate_workout_plan(
    data: OnboardingData,
    session_history: Optional[str] = None,
    db: Optional[Session] = None,
) -> WorkoutPlan:
    """
    Retrieve relevant KB chunks, then call Groq to generate a grounded plan.

    Args:
        data:            OnboardingData from the request.
        session_history: Optional recent session summary for personalisation.
        db:              SQLAlchemy Session.  When provided, retrieval runs and
                         the plan is grounded against KB chunks.  When None
                         (tests, fallback), generation proceeds without retrieval.

    Raises:
        ValueError: if the model returns malformed JSON or missing fields.
        APIError:   if the Groq API call fails.
    """
    # ── RAG retrieval — three structurally distinct paths ─────────────────────
    #
    #  "no_retrieval"   db=None  → skip retrieval; pre-RAG compatibility path.
    #                             No context block, no grounded/citation prompt
    #                             instructions; schema defaults (True, []) stand.
    #  "grounded"       db set, retrieval succeeded with high confidence.
    #                             KB chunks injected; model instructed to cite.
    #  "low_confidence" db set, retrieval found nothing useful.
    #                             Fallback note injected; model instructed to
    #                             declare grounded=false.

    generation_mode: str = "no_retrieval"
    retrieval_result = None
    context_block: Optional[str] = None

    if db is not None:
        from app.services.retrieval_service import retrieve
        query = _build_retrieval_query(data)
        logger.info("Retrieving KB chunks for query: %r", query)
        retrieval_result = retrieve(query, data, k=5, db=db)

        if retrieval_result.low_confidence:
            logger.info("Retrieval low_confidence — injecting fallback note")
            generation_mode = "low_confidence"
            context_block = _LOW_CONFIDENCE_BLOCK
        else:
            generation_mode = "grounded"
            context_block = _build_context_block(retrieval_result.chunks)
            logger.info("Injecting %d KB chunks into prompt", len(retrieval_result.chunks))

    client = _get_client()

    logger.info(
        "Generating workout plan for %s (goal=%s, level=%s, days=%d, mode=%s)",
        data.name, data.fitness_goal, data.fitness_level, data.days_per_week,
        generation_mode,
    )

    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": _build_system_prompt(generation_mode)},
                {"role": "user",   "content": _build_user_prompt(data, session_history, context_block)},
            ],
        )
    except APIError as exc:
        logger.error("Groq API error: %s", exc)
        raise

    raw_text = completion.choices[0].message.content.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        plan_dict = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Groq returned non-JSON response: %s", raw_text[:500])
        raise ValueError(f"Could not parse Groq's response as JSON: {exc}") from exc

    # Override grounded server-side — the model cannot reliably introspect its
    # own knowledge quality; the retrieval confidence signal is authoritative.
    #
    # Three branches mirror the three generation_mode values above:
    if generation_mode == "grounded":
        plan_dict["grounded"] = True       # retrieval confirmed confidence
    elif generation_mode == "low_confidence":
        plan_dict["grounded"] = False      # retrieval signalled low confidence
        plan_dict["citations"] = []        # discard any model-hallucinated citations
    else:
        # "no_retrieval": db=None, pre-RAG compatibility path.
        # No real chunks were cited, so any model-generated citation text is
        # hallucinated — discard it.  grounded stays True (no retrieval signal
        # means we make no low-confidence claim; field is semantically N/A here).
        plan_dict["grounded"] = True
        plan_dict["citations"] = []

    try:
        plan = WorkoutPlan(**plan_dict)
    except Exception as exc:
        logger.error("Groq JSON did not match WorkoutPlan schema: %s", exc)
        raise ValueError(f"Groq response schema mismatch: {exc}") from exc

    logger.info("Successfully generated plan: %s (grounded=%s)", plan.title, plan.grounded)
    return plan
