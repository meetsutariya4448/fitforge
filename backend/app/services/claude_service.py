"""
Groq API service for AI workout plan generation.

Responsible for:
  1. Building a structured prompt from onboarding data
  2. Calling the Groq API (OpenAI-compatible chat completions)
  3. Parsing the JSON response into WorkoutPlan schema objects

Separation of concerns: the router calls this service; the service owns
all AI-specific logic so it can be swapped or tested independently.
"""

import json
import logging
from groq import Groq, APIError

from app.config import settings
from app.schemas.workout import OnboardingData, WorkoutPlan, WorkoutDay, Exercise

logger = logging.getLogger(__name__)

# Lazily initialised so the app can start even without an API key set
_client: Groq | None = None


def _get_client() -> Groq:
    """Return (or create) the shared Groq client."""
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    return (
        "You are FitForge AI, an expert personal trainer and sports scientist. "
        "Your task is to create personalised, safe, and effective weekly workout plans. "
        "Always return valid JSON that matches the schema described in the user message. "
        "Do NOT include markdown code fences — return raw JSON only."
    )


def _build_user_prompt(data: OnboardingData, session_history: str = None) -> str:
    equipment_str = ", ".join(e.value.replace("_", " ") for e in data.available_equipment)
    goal_str = data.fitness_goal.value.replace("_", " ")
    level_str = data.fitness_level.value

    prompt = f"""
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

async def generate_workout_plan(data: OnboardingData, session_history: str = None) -> WorkoutPlan:
    """
    Call Groq to generate a workout plan from onboarding data.

    Raises:
        ValueError: if the model returns malformed JSON or missing fields
        APIError: if the Groq API call fails
    """
    client = _get_client()

    logger.info(
        "Generating workout plan for %s (goal=%s, level=%s, days=%d)",
        data.name, data.fitness_goal, data.fitness_level, data.days_per_week,
    )

    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_prompt(data, session_history)},
            ],
        )
    except APIError as exc:
        logger.error("Groq API error: %s", exc)
        raise

    raw_text = completion.choices[0].message.content.strip()

    # Strip markdown fences if the model adds them despite instructions
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

    # Validate and coerce into our Pydantic schema
    try:
        plan = WorkoutPlan(**plan_dict)
    except Exception as exc:
        logger.error("Groq JSON did not match WorkoutPlan schema: %s", exc)
        raise ValueError(f"Groq response schema mismatch: {exc}") from exc

    logger.info("Successfully generated plan: %s", plan.title)
    return plan
