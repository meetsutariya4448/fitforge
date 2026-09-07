"""
Unit tests for agent_service.py.

13 pure-function tests (no DB, no live model calls — Groq client is monkeypatched)
+ 1 graph integration test (real compiled graph, mocked node functions).
"""

import json
import logging
from unittest.mock import AsyncMock

import pytest

from app.schemas.workout import Equipment, FitnessGoal, FitnessLevel, OnboardingData


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_onboarding(**overrides):
    defaults = dict(
        name="Alex",
        age=28,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        fitness_level=FitnessLevel.BEGINNER,
        available_equipment=[Equipment.DUMBBELLS],
        days_per_week=3,
    )
    defaults.update(overrides)
    return OnboardingData(**defaults)


def _minimal_plan_dict(**overrides):
    base = {
        "title": "Test Plan",
        "summary": "A solid beginner plan.",
        "generated_for": "Alex",
        "general_tips": ["Eat well", "Sleep 8h"],
        "citations": [],
        "grounded": True,
        "days": [
            {
                "day": "Day 1",
                "focus": "Full Body",
                "duration_minutes": 45,
                "exercises": [
                    {"name": "Squat", "sets": 3, "reps": "8-10", "rest_seconds": 90, "notes": ""}
                ],
            }
        ],
    }
    base.update(overrides)
    return base


def _make_critique_state(
    plan_dict=None,
    best_score=0.0,
    best_plan_dict=None,
    iteration=0,
):
    return {
        "onboarding_data": _make_onboarding(),
        "session_history": None,
        "db": None,
        "generation_mode": "grounded",
        "context_block": None,
        "plan_dict": plan_dict or _minimal_plan_dict(),
        "best_plan_dict": best_plan_dict,
        "best_score": best_score,
        "critique": None,
        "iteration": iteration,
    }


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


def _patch_groq(monkeypatch, content: str):
    """Replace _get_client in agent_service with a fake returning `content`."""
    import app.services.agent_service as svc

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeCompletion(content)

    class _FakeClient:
        chat = type("Chat", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(svc, "_get_client", lambda: _FakeClient())


# ---------------------------------------------------------------------------
# route_after_critique — pure function, no mocks
# ---------------------------------------------------------------------------

class TestRouteAfterCritique:
    def _make_state(self, accepted, iteration):
        return {
            "critique": {"accepted": accepted},
            "iteration": iteration,
        }

    def test_route_accepts_when_score_above_threshold(self, monkeypatch):
        from app.services.agent_service import route_after_critique
        monkeypatch.setattr("app.services.agent_service.settings.agent_max_iterations", 2)
        state = self._make_state(accepted=True, iteration=0)
        assert route_after_critique(state) == "__end__"

    def test_route_rejects_when_score_below_threshold(self, monkeypatch):
        from app.services.agent_service import route_after_critique
        monkeypatch.setattr("app.services.agent_service.settings.agent_max_iterations", 2)
        state = self._make_state(accepted=False, iteration=0)
        assert route_after_critique(state) == "refine"

    def test_route_accepts_on_budget_exhaustion(self, monkeypatch):
        from app.services.agent_service import route_after_critique
        monkeypatch.setattr("app.services.agent_service.settings.agent_max_iterations", 2)
        state = self._make_state(accepted=False, iteration=2)
        assert route_after_critique(state) == "__end__"


# ---------------------------------------------------------------------------
# critique_node — acceptance logic (mocked Groq)
# ---------------------------------------------------------------------------

class TestCritiqueAcceptance:
    @pytest.mark.asyncio
    async def test_critique_acceptance_high_score_no_violation(self, monkeypatch):
        from app.services.agent_service import critique_node
        monkeypatch.setattr("app.services.agent_service.settings.agent_critique_threshold", 0.75)
        _patch_groq(monkeypatch, json.dumps({"score": 0.9, "issues": []}))
        result = await critique_node(_make_critique_state())
        assert result["critique"]["accepted"] is True
        assert result["critique"]["equipment_violation"] is False

    @pytest.mark.asyncio
    async def test_critique_acceptance_equipment_violation_overrides_score(self, monkeypatch):
        """score=0.9 above threshold but equipment violation forces accepted=False."""
        from app.services.agent_service import critique_node
        monkeypatch.setattr("app.services.agent_service.settings.agent_critique_threshold", 0.75)
        payload = json.dumps({
            "score": 0.9,
            "issues": [{"category": "equipment", "detail": "Barbell required"}],
        })
        _patch_groq(monkeypatch, payload)
        result = await critique_node(_make_critique_state())
        assert result["critique"]["equipment_violation"] is True
        assert result["critique"]["accepted"] is False

    @pytest.mark.asyncio
    async def test_critique_acceptance_unknown_category_dropped(self, monkeypatch):
        """Issues with unknown categories are filtered; don't trigger equipment_violation."""
        from app.services.agent_service import critique_node
        monkeypatch.setattr("app.services.agent_service.settings.agent_critique_threshold", 0.75)
        payload = json.dumps({
            "score": 0.9,
            "issues": [{"category": "unknown", "detail": "This should be ignored"}],
        })
        _patch_groq(monkeypatch, payload)
        result = await critique_node(_make_critique_state())
        assert result["critique"]["issues"] == []
        assert result["critique"]["equipment_violation"] is False
        assert result["critique"]["accepted"] is True

    @pytest.mark.asyncio
    async def test_critique_fails_open_on_bad_json(self, monkeypatch):
        """Unparseable critic JSON → accepted=True, parse_error=True (fail-open)."""
        from app.services.agent_service import critique_node
        _patch_groq(monkeypatch, "not valid json at all {{{")
        result = await critique_node(_make_critique_state())
        assert result["critique"]["accepted"] is True
        assert result["critique"].get("parse_error") is True

    @pytest.mark.asyncio
    async def test_critique_fails_open_structured_log_emitted(self, monkeypatch, caplog):
        """Parse-error path emits log.info (not just log.warning) with parse_error=1."""
        from app.services.agent_service import critique_node
        _patch_groq(monkeypatch, "}")
        with caplog.at_level(logging.INFO, logger="app.services.agent_service"):
            await critique_node(_make_critique_state())
        assert any("parse_error=1" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# critique_node — best plan tracking
# ---------------------------------------------------------------------------

class TestBestPlanTracking:
    @pytest.mark.asyncio
    async def test_best_plan_tracks_highest_score(self, monkeypatch):
        """critique called with score=0.6 then 0.8 → best_plan_dict updated on second call."""
        from app.services.agent_service import critique_node
        monkeypatch.setattr("app.services.agent_service.settings.agent_critique_threshold", 0.75)

        plan_a = _minimal_plan_dict(title="Plan A")
        plan_b = _minimal_plan_dict(title="Plan B")

        # First critique: score 0.6, starts from best_score=0.0
        _patch_groq(monkeypatch, json.dumps({"score": 0.6, "issues": []}))
        state1 = _make_critique_state(plan_dict=plan_a, best_score=0.0)
        r1 = await critique_node(state1)
        assert r1.get("best_plan_dict") == plan_a
        assert r1.get("best_score") == pytest.approx(0.6)

        # Second critique: score 0.8, starts from best_score=0.6
        _patch_groq(monkeypatch, json.dumps({"score": 0.8, "issues": []}))
        state2 = _make_critique_state(plan_dict=plan_b, best_score=0.6, best_plan_dict=plan_a)
        r2 = await critique_node(state2)
        assert r2.get("best_plan_dict") == plan_b
        assert r2.get("best_score") == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# run_agent — final state processing (mocked ainvoke)
# ---------------------------------------------------------------------------

def _make_final_state(plan_dict, best_plan_dict, best_score=0.8, generation_mode="no_retrieval", iteration=1):
    return {
        "onboarding_data": _make_onboarding(),
        "session_history": None,
        "db": None,
        "generation_mode": generation_mode,
        "context_block": None,
        "plan_dict": plan_dict,
        "best_plan_dict": best_plan_dict,
        "best_score": best_score,
        "critique": {"score": best_score, "accepted": True, "issues": [], "equipment_violation": False},
        "iteration": iteration,
    }


class TestRunAgent:
    @pytest.mark.asyncio
    async def test_run_agent_returns_best_not_last(self, monkeypatch):
        """run_agent returns best_plan_dict (highest score), not plan_dict (last)."""
        import app.services.agent_service as svc
        plan_a = _minimal_plan_dict(title="Best Plan")
        plan_b = _minimal_plan_dict(title="Last Plan")
        fake_state = _make_final_state(plan_dict=plan_b, best_plan_dict=plan_a, best_score=0.8)
        monkeypatch.setattr(svc.agent_graph, "ainvoke", AsyncMock(return_value=fake_state))

        result = await svc.run_agent(data=_make_onboarding(), db=None)
        assert result.title == "Best Plan"

    @pytest.mark.asyncio
    async def test_run_agent_stamps_grounded_correctly(self, monkeypatch):
        """generation_mode='grounded' → plan.grounded=True."""
        import app.services.agent_service as svc
        plan = _minimal_plan_dict(grounded=False)
        fake_state = _make_final_state(plan_dict=plan, best_plan_dict=plan, generation_mode="grounded")
        monkeypatch.setattr(svc.agent_graph, "ainvoke", AsyncMock(return_value=fake_state))

        result = await svc.run_agent(data=_make_onboarding(), db=None)
        assert result.grounded is True

    @pytest.mark.asyncio
    async def test_run_agent_stamps_low_confidence_correctly(self, monkeypatch):
        """generation_mode='low_confidence' → plan.grounded=False, plan.citations=[]."""
        import app.services.agent_service as svc
        plan = _minimal_plan_dict(grounded=True, citations=["[1] some chunk"])
        fake_state = _make_final_state(
            plan_dict=plan, best_plan_dict=plan, generation_mode="low_confidence"
        )
        monkeypatch.setattr(svc.agent_graph, "ainvoke", AsyncMock(return_value=fake_state))

        result = await svc.run_agent(data=_make_onboarding(), db=None)
        assert result.grounded is False
        assert result.citations == []


# ---------------------------------------------------------------------------
# retrieve_node — db=None guard
# ---------------------------------------------------------------------------

class TestRetrieveNode:
    def test_retrieve_node_skips_retrieval_when_db_none(self, monkeypatch):
        """db=None → generation_mode='no_retrieval', context_block=None, no retrieve() call."""
        import app.services.agent_service as svc
        retrieve_called = {"n": 0}

        def fake_retrieve(*args, **kwargs):
            retrieve_called["n"] += 1

        monkeypatch.setattr(svc, "retrieve", fake_retrieve)

        state = {
            "db": None,
            "onboarding_data": _make_onboarding(),
        }
        result = svc.retrieve_node(state)
        assert result["generation_mode"] == "no_retrieval"
        assert result["context_block"] is None
        assert retrieve_called["n"] == 0


# ---------------------------------------------------------------------------
# Graph integration test — real compiled graph, mocked node functions
# ---------------------------------------------------------------------------

class TestGraphIntegration:
    @pytest.mark.asyncio
    async def test_graph_calls_refine_exactly_once_on_single_rejection(self, monkeypatch):
        """Compile the real graph with patched async nodes.

        Critic rejects on iteration=0 (score=0.4), accepts on iteration=1 (score=0.8).
        Assert: refine_node called exactly once, critique_node called exactly twice.
        """
        import app.services.agent_service as svc

        refine_calls = {"n": 0}
        critique_calls = {"n": 0}
        fake_plan = _minimal_plan_dict()

        async def fake_retrieve(state):
            return {"generation_mode": "grounded", "context_block": "[1] chunk"}

        async def fake_generate(state):
            return {"plan_dict": fake_plan}

        async def fake_critique(state):
            critique_calls["n"] += 1
            if critique_calls["n"] == 1:
                score, accepted = 0.4, False
                best_update = {}
            else:
                score, accepted = 0.8, True
                best_update = {"best_plan_dict": fake_plan, "best_score": 0.8}
            return {
                "critique": {
                    "score": score,
                    "accepted": accepted,
                    "equipment_violation": False,
                    "issues": [],
                },
                **best_update,
            }

        async def fake_refine(state):
            refine_calls["n"] += 1
            return {"plan_dict": fake_plan, "iteration": state["iteration"] + 1}

        monkeypatch.setattr(svc, "retrieve_node", fake_retrieve)
        monkeypatch.setattr(svc, "generate_node", fake_generate)
        monkeypatch.setattr(svc, "critique_node", fake_critique)
        monkeypatch.setattr(svc, "refine_node", fake_refine)
        # Recompile with patched node functions; monkeypatch restores after the test
        monkeypatch.setattr(svc, "agent_graph", svc._build_graph())

        monkeypatch.setattr("app.services.agent_service.settings.agent_max_iterations", 2)

        result = await svc.run_agent(data=_make_onboarding(), db=None)

        assert refine_calls["n"] == 1
        assert critique_calls["n"] == 2
        assert result.title == fake_plan["title"]
