"""
Unit tests for ai_service.py (Phase 3 grounded generation).

No real Groq calls — the Groq client is monkeypatched with a fake that
returns a preset JSON string.  No real DB or embedding model either.
"""

import json
import pytest

from app.schemas.workout import (
    OnboardingData, FitnessGoal, FitnessLevel, Equipment, WorkoutPlan,
)
from app.services.ai_service import (
    _build_context_block,
    _build_retrieval_query,
    _build_system_prompt,
    _build_user_prompt,
    _LOW_CONFIDENCE_BLOCK,
    generate_workout_plan,
)
from app.services.retrieval_service import ChunkResult, RetrievalResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_onboarding(**overrides):
    defaults = dict(
        name="Alex", age=28,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        fitness_level=FitnessLevel.BEGINNER,
        available_equipment=[Equipment.DUMBBELLS],
        days_per_week=3,
    )
    defaults.update(overrides)
    return OnboardingData(**defaults)


def _make_chunk(chunk_id, raw, ctx="context blurb"):
    return ChunkResult(
        chunk_id=chunk_id, raw_content=raw,
        contextualized_content=ctx, metadata={}, score=0.9,
    )


def _make_retrieval_result(chunks, low_confidence=False):
    return RetrievalResult(
        chunks=chunks,
        scores=[c.score for c in chunks],
        low_confidence=low_confidence,
        retrieval_mode="hybrid_rerank",
    )


def _minimal_plan_dict(**overrides):
    """Return the minimal dict that WorkoutPlan(**d) accepts."""
    base = {
        "title": "Test Plan",
        "summary": "A solid beginner plan.",
        "generated_for": "Alex",
        "general_tips": ["Eat well", "Sleep 8h"],
        "days": [
            {
                "day": "Day 1", "focus": "Full Body",
                "duration_minutes": 45,
                "exercises": [{"name": "Squat", "sets": 3, "reps": "8-10",
                               "rest_seconds": 90, "notes": "Keep chest up"}],
            }
        ],
    }
    base.update(overrides)
    return base


class FakeCompletion:
    """Mimics the minimal shape of a Groq chat completion response."""
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


def _make_fake_groq(plan_dict):
    """Return a fake Groq client whose create() returns plan_dict as JSON."""
    class FakeCreate:
        def create(self, **kwargs):
            return FakeCompletion(json.dumps(plan_dict))

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCreate()})()

    return FakeClient()


# ── Schema / backward-compat tests ───────────────────────────────────────────

class TestWorkoutPlanSchema:
    def test_citations_default_empty_on_old_plan(self):
        """Old plan dicts without citations/grounded keys must deserialise safely."""
        old_dict = _minimal_plan_dict()  # no citations / grounded keys
        plan = WorkoutPlan(**old_dict)
        assert plan.citations == []
        assert plan.grounded is True

    def test_citations_and_grounded_round_trip(self):
        plan = WorkoutPlan(**_minimal_plan_dict(
            citations=["[1] ACSM beginner volume"], grounded=True,
        ))
        dumped = plan.model_dump()
        assert dumped["citations"] == ["[1] ACSM beginner volume"]
        assert dumped["grounded"] is True

    def test_grounded_false_stored_correctly(self):
        plan = WorkoutPlan(**_minimal_plan_dict(grounded=False, citations=[]))
        assert plan.grounded is False


# ── Prompt builder tests ──────────────────────────────────────────────────────

class TestPromptBuilders:
    def test_context_block_uses_raw_not_contextualized(self):
        """raw_content must appear in the block; contextualized_content must not."""
        chunks = [
            _make_chunk(1, "raw text A", ctx="CONTEXT BLURB A"),
            _make_chunk(2, "raw text B", ctx="CONTEXT BLURB B"),
        ]
        block = _build_context_block(chunks)
        assert "raw text A" in block
        assert "raw text B" in block
        assert "CONTEXT BLURB A" not in block
        assert "CONTEXT BLURB B" not in block

    def test_context_block_numbering(self):
        chunks = [_make_chunk(i, f"chunk content {i}") for i in range(1, 4)]
        block = _build_context_block(chunks)
        assert "[1]" in block
        assert "[2]" in block
        assert "[3]" in block

    def test_system_prompt_grounded_mode_mentions_citation(self):
        prompt = _build_system_prompt("grounded")
        assert "cite" in prompt.lower() or "citation" in prompt.lower()
        assert "grounded" in prompt.lower()

    def test_system_prompt_low_confidence_sets_grounded_false(self):
        prompt = _build_system_prompt("low_confidence")
        assert "false" in prompt.lower()
        assert "grounded" in prompt.lower()

    def test_system_prompt_no_retrieval_omits_grounded_instructions(self):
        """db=None path must not instruct the model to set grounded=false."""
        prompt = _build_system_prompt("no_retrieval")
        assert "grounded" not in prompt.lower()
        assert "citations" not in prompt.lower()

    def test_user_prompt_injects_context_block(self):
        data = _make_onboarding()
        block = "[KNOWLEDGE BASE CONTEXT]\n[1] sets per week guidelines"
        prompt = _build_user_prompt(data, session_history=None, context_block=block)
        assert "[KNOWLEDGE BASE CONTEXT]" in prompt
        assert "sets per week guidelines" in prompt

    def test_user_prompt_no_context_block_skips_section(self):
        data = _make_onboarding()
        prompt = _build_user_prompt(data, session_history=None, context_block=None)
        assert "[KNOWLEDGE BASE CONTEXT]" not in prompt

    def test_low_confidence_block_injected_on_low_confidence(self):
        """When retrieval returns low_confidence=True the fallback block must appear."""
        data = _make_onboarding()
        prompt = _build_user_prompt(
            data, session_history=None, context_block=_LOW_CONFIDENCE_BLOCK,
        )
        assert "No high-confidence reference material" in prompt

    def test_retrieval_query_includes_goal_and_level(self):
        data = _make_onboarding(
            fitness_goal=FitnessGoal.LOSE_WEIGHT,
            fitness_level=FitnessLevel.INTERMEDIATE,
        )
        q = _build_retrieval_query(data)
        assert "lose weight" in q
        assert "intermediate" in q


# ── generate_workout_plan integration tests (all mocked) ─────────────────────

class TestGenerateWorkoutPlan:
    def _patch_groq(self, monkeypatch, plan_dict):
        import app.services.ai_service as svc
        monkeypatch.setattr(svc, "_client", _make_fake_groq(plan_dict))

    def _patch_retrieve(self, monkeypatch, result: RetrievalResult):
        import app.services.ai_service as svc

        def fake_retrieve(*args, **kwargs):
            return result

        monkeypatch.setattr(svc, "retrieve", fake_retrieve, raising=False)
        # Also patch into retrieval_service namespace so the lazy import resolves
        import app.services.retrieval_service as rsvc
        monkeypatch.setattr(rsvc, "retrieve", fake_retrieve, raising=False)

    @pytest.mark.asyncio
    async def test_generate_without_db_skips_retrieval(self, monkeypatch):
        """db=None must bypass retrieval entirely and leave grounded=True (schema default)."""
        retrieved = {"called": False}

        import app.services.ai_service as svc

        def should_not_be_called(*a, **kw):
            retrieved["called"] = True
            return _make_retrieval_result([])

        monkeypatch.setattr(svc, "retrieve", should_not_be_called, raising=False)

        plan_dict = _minimal_plan_dict(grounded=True, citations=["[1] something"])
        self._patch_groq(monkeypatch, plan_dict)

        plan = await generate_workout_plan(_make_onboarding(), db=None)

        assert not retrieved["called"], "retrieve() was called despite db=None"
        assert plan.grounded is True  # no retrieval signal → schema default stands

    @pytest.mark.asyncio
    async def test_grounded_overridden_server_side_high_confidence(self, monkeypatch):
        """Model returns grounded=false but retrieval is high-confidence → True."""
        chunks = [_make_chunk(1, "ACSM sets per week for beginners")]
        rr = _make_retrieval_result(chunks, low_confidence=False)

        plan_dict = _minimal_plan_dict(grounded=False, citations=[])  # model lies
        self._patch_groq(monkeypatch, plan_dict)

        import app.services.ai_service as svc
        monkeypatch.setattr(svc, "_client", _make_fake_groq(plan_dict))

        class FakeDB:
            pass

        fake_db = FakeDB()

        def fake_retrieve(*a, **kw):
            return rr

        import app.services.retrieval_service as rsvc
        monkeypatch.setattr(rsvc, "retrieve", fake_retrieve, raising=False)

        # Patch the lazy import inside generate_workout_plan
        import builtins
        real_import = builtins.__import__

        def patched_import(name, *args, **kwargs):
            mod = real_import(name, *args, **kwargs)
            if name == "app.services.retrieval_service":
                mod.retrieve = fake_retrieve
            return mod

        monkeypatch.setattr(builtins, "__import__", patched_import)

        plan = await generate_workout_plan(_make_onboarding(), db=fake_db)
        assert plan.grounded is True, (
            "grounded should be True (retrieval was high-confidence) "
            "even though model returned grounded=false"
        )

    @pytest.mark.asyncio
    async def test_grounded_false_when_low_confidence(self, monkeypatch):
        """Low-confidence retrieval must produce grounded=False on the plan."""
        chunks = [_make_chunk(1, "some chunk")]
        rr = _make_retrieval_result(chunks, low_confidence=True)

        plan_dict = _minimal_plan_dict(grounded=True, citations=["[1] something"])
        self._patch_groq(monkeypatch, plan_dict)

        class FakeDB:
            pass

        fake_db = FakeDB()
        fake_retrieve = lambda *a, **kw: rr

        import app.services.retrieval_service as rsvc
        import builtins
        real_import = builtins.__import__

        def patched_import(name, *args, **kwargs):
            mod = real_import(name, *args, **kwargs)
            if name == "app.services.retrieval_service":
                mod.retrieve = fake_retrieve
            return mod

        monkeypatch.setattr(builtins, "__import__", patched_import)

        plan = await generate_workout_plan(_make_onboarding(), db=fake_db)
        assert plan.grounded is False

    @pytest.mark.asyncio
    async def test_plan_has_default_citations_on_no_db(self, monkeypatch):
        """When db=None, citations must default to [] (not blow up on missing key)."""
        plan_dict = _minimal_plan_dict()  # no citations key at all
        self._patch_groq(monkeypatch, plan_dict)
        plan = await generate_workout_plan(_make_onboarding(), db=None)
        assert plan.citations == []

    @pytest.mark.asyncio
    async def test_db_none_is_distinct_from_low_confidence(self, monkeypatch):
        """
        db=None and low_confidence=True must be structurally distinct paths:

        1. The system prompt sent to Groq must differ — db=None must NOT
           contain 'grounded' or 'citations' instructions (only low_confidence does).
        2. The user prompt for db=None must NOT contain the low-confidence
           fallback block text.
        3. grounded must be True for db=None, False for low_confidence.
        """
        import app.services.ai_service as svc

        captured_messages = {"no_retrieval": None, "low_confidence": None}

        class CapturingGroq:
            def __init__(self, label):
                self._label = label

            class chat:
                class completions:
                    pass

            def _create(self, **kwargs):
                captured_messages[self._label] = kwargs.get("messages", [])
                plan_dict = _minimal_plan_dict(grounded=True, citations=[])
                return FakeCompletion(json.dumps(plan_dict))

        # ── Scenario A: db=None ──────────────────────────────────────────────
        messages_no_retrieval = []

        class FakeGroqNoRetrieval:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        messages_no_retrieval.extend(kwargs.get("messages", []))
                        return FakeCompletion(json.dumps(_minimal_plan_dict(grounded=True, citations=[])))

        monkeypatch.setattr(svc, "_client", FakeGroqNoRetrieval())
        plan_no_db = await generate_workout_plan(_make_onboarding(), db=None)

        # ── Scenario B: db provided, low_confidence=True ─────────────────────
        messages_low_conf = []

        class FakeGroqLowConf:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        messages_low_conf.extend(kwargs.get("messages", []))
                        return FakeCompletion(json.dumps(_minimal_plan_dict(grounded=False, citations=[])))

        monkeypatch.setattr(svc, "_client", FakeGroqLowConf())

        class FakeDB:
            pass

        lc_result = _make_retrieval_result([], low_confidence=True)

        import builtins
        real_import = builtins.__import__

        def patched_import(name, *a, **kw):
            mod = real_import(name, *a, **kw)
            if name == "app.services.retrieval_service":
                mod.retrieve = lambda *a, **kw: lc_result
            return mod

        monkeypatch.setattr(builtins, "__import__", patched_import)
        plan_low_conf = await generate_workout_plan(_make_onboarding(), db=FakeDB())

        # ── Assertions ───────────────────────────────────────────────────────
        assert messages_no_retrieval, "Groq was never called for db=None scenario"
        assert messages_low_conf, "Groq was never called for low_confidence scenario"

        sys_no_retrieval = next(m["content"] for m in messages_no_retrieval if m["role"] == "system")
        sys_low_conf     = next(m["content"] for m in messages_low_conf     if m["role"] == "system")
        usr_no_retrieval = next(m["content"] for m in messages_no_retrieval if m["role"] == "user")
        usr_low_conf     = next(m["content"] for m in messages_low_conf     if m["role"] == "user")

        # System prompt: db=None must NOT contain grounded/citation instructions
        assert "grounded" not in sys_no_retrieval.lower(), (
            f"db=None system prompt must not mention 'grounded'; got:\n{sys_no_retrieval}"
        )
        assert "citations" not in sys_no_retrieval.lower(), (
            f"db=None system prompt must not mention 'citations'; got:\n{sys_no_retrieval}"
        )

        # System prompt: low_confidence MUST instruct grounded=false
        assert "false" in sys_low_conf.lower(), (
            f"low_confidence system prompt must say 'false'; got:\n{sys_low_conf}"
        )

        # User prompt: low_confidence fallback text must appear only in low_conf path
        assert "No high-confidence reference material" in usr_low_conf, (
            "low_confidence user prompt must contain the fallback block"
        )
        assert "No high-confidence reference material" not in usr_no_retrieval, (
            "db=None user prompt must NOT contain the low-confidence fallback block"
        )

        # grounded must differ between the two paths
        assert plan_no_db.grounded is True, (
            f"db=None plan must have grounded=True (schema default), got {plan_no_db.grounded}"
        )
        assert plan_low_conf.grounded is False, (
            f"low_confidence plan must have grounded=False, got {plan_low_conf.grounded}"
        )

    @pytest.mark.asyncio
    async def test_markdown_fence_stripped(self, monkeypatch):
        """Model response wrapped in ```json ... ``` must still parse correctly."""
        import app.services.ai_service as svc
        plan_dict = _minimal_plan_dict(grounded=False, citations=[])
        fenced = "```json\n" + json.dumps(plan_dict) + "\n```"

        class FakeGroqFenced:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return FakeCompletion(fenced)

        monkeypatch.setattr(svc, "_client", FakeGroqFenced())
        plan = await generate_workout_plan(_make_onboarding(), db=None)
        assert plan.title == "Test Plan"
