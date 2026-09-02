# FitForge — AI Fitness Platform

[![CI](https://github.com/meetsutariya4448/fitforge/actions/workflows/ci.yml/badge.svg)](https://github.com/meetsutariya4448/fitforge/actions/workflows/ci.yml)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-fitforge--six.vercel.app-brand?style=flat-square&color=10b981)](https://fitforge-six.vercel.app)
[![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org)
[![Groq AI](https://img.shields.io/badge/Groq-Llama%203.3%2070B-orange?style=flat-square)](https://groq.com)

---

## Overview

FitForge is a full-stack AI fitness platform that generates personalised weekly workout plans in seconds. Users describe their goals, fitness level, and available equipment across a 5-step onboarding flow, then receive a structured, day-by-day plan produced by Groq's Llama 3.3 70B model. Every plan is saved to their account so they can revisit past plans, log completed workouts with sets, reps, and weight, and track progress through an interactive dashboard with strength trend charts and personal record tracking.

🔗 **Live demo:** [https://fitforge-six.vercel.app](https://fitforge-six.vercel.app)
🔑 **Demo login:** `demo@fitforge.app` / `Demo1234!`

---

## Features

### Module 1 — AI Workout Planner
- 5-step onboarding wizard (name, goal, level, equipment, schedule)
- AI plan generation via **Groq API** (Llama 3.3 70B Versatile)
- Collapsible animated day cards with exercises, sets, reps, warmup/cooldown notes
- Plans saved to PostgreSQL — revisit any past plan without regenerating

### Module 2 — Progress Tracker
- **Workout logging** — log sets, reps, and weight per exercise from any plan
- **Personal Records (PRs)** — automatically tracked per exercise; updates whenever a new weight or reps best is set
- **Progress dashboard** — 4 stat cards, volume over time chart, weekly consistency chart, top-5 exercises chart
- **Strength trend chart** — per-exercise line chart showing weight progression over time

### Access
- Demo account available instantly — no signup required
- Full JWT-authenticated accounts with 30-minute access tokens + 30-day rotating refresh tokens
- Silent token refresh via Axios interceptor — users stay logged in without interruption

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, React Router v6, Tailwind CSS, Framer Motion, Recharts |
| **Backend** | Python 3.11, FastAPI 0.111, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 16, Alembic migrations |
| **AI** | Groq API — Llama 3.3 70B Versatile |
| **Auth** | JWT (python-jose HS256), bcrypt password hashing |
| **Deployment** | Frontend → Vercel · Backend → Render |
| **DevOps** | Docker + docker-compose for local Postgres |

---

## Live Demo

**URL:** [https://fitforge-six.vercel.app](https://fitforge-six.vercel.app)

**Demo credentials:**
```
Email:    demo@fitforge.app
Password: Demo1234!
```

The demo account is pre-seeded with 5 workout sessions, 9 personal records, and populated charts so you can see the full dashboard immediately.

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or use Docker)

### 1. Clone
```bash
git clone https://github.com/meetsutariya4448/fitforge.git
cd fitforge
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in DATABASE_URL, SECRET_KEY, GROQ_API_KEY in .env

alembic upgrade head             # Run all migrations
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` · Docs: `http://localhost:8000/docs`

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env
# VITE_API_BASE_URL is blank for local dev (Vite proxy handles it)
npm run dev
```

App: `http://localhost:5173`

### 4. Seed demo data (optional)
```bash
cd backend
source venv/bin/activate
python -m scripts.seed_demo
```

### Docker (alternative)
```bash
docker compose up --build   # starts Postgres + backend
cd frontend && npm run dev  # frontend separately
```

---

## Testing

CI runs three jobs on every push — unit tests, integration tests (real Postgres), and a frontend build. All three must pass for the badge to go green.

**Unit tests** — mock all external services; no database needed:
```bash
cd backend
pytest tests/test_retrieval.py tests/test_generation.py tests/test_agent.py -v
```

**Integration tests** — hit real HTTP endpoints against a real PostgreSQL database:
```bash
cd backend
# 1. Start Postgres (e.g. via docker compose up -d)
# 2. Set DATABASE_URL, SECRET_KEY, GROQ_API_KEY in your environment or .env
alembic upgrade head
pytest tests/test_api.py -v
```

The integration suite covers: auth (register, login, refresh, logout, delete account), authorization boundaries (user A cannot read user B's sessions or PRs), PR upsert boundary logic (strict greater-than), cursor pagination on `/history`, and Groq graceful-failure handling. The Groq client is monkeypatched — no live API calls are made and no API key is required.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | Random secret for signing JWTs |
| `GROQ_API_KEY` | ✅ | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | | Model ID (default: `llama-3.3-70b-versatile`) |
| `APP_ENV` | | `development` or `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | Access token lifetime in minutes (default: `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | | Refresh token lifetime in days (default: `30`) |
| `AGENT_MAX_ITERATIONS` | | Max refine cycles per agent request (default: `2`) |
| `AGENT_CRITIQUE_THRESHOLD` | | Score ≥ this → plan accepted without refining (default: `0.75`) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | ✅ (production) | Backend URL e.g. `https://your-app.onrender.com` |

---

## API Reference

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/api/auth/register` | — | Create account, returns JWT + refresh token |
| `POST` | `/api/auth/login` | — | Login, returns JWT + refresh token |
| `POST` | `/api/auth/refresh` | — | Rotate refresh token, returns new JWT pair |
| `POST` | `/api/auth/logout` | — | Revoke refresh token (server-side session end) |
| `GET` | `/api/auth/me` | ✅ | Current user profile |
| `DELETE` | `/api/auth/me` | ✅ | Delete account + purge all user data (password required) |
| `POST` | `/api/workout/generate` | ✅ | AI plan generation + save to DB |
| `POST` | `/api/workout/generate-agent` | ✅ | Agent critique loop — generate + self-reflect + refine |
| `GET` | `/api/workout/history` | ✅ | Saved plans, cursor-paginated (`?cursor=<id>&limit=20`) |
| `POST` | `/api/sessions` | ✅ | Log workout session (auto-upserts PRs) |
| `GET` | `/api/sessions` | ✅ | All sessions for user |
| `GET` | `/api/sessions/exercise/{name}` | ✅ | Per-exercise strength trend data |
| `GET` | `/api/sessions/{id}` | ✅ | Single session by ID |
| `GET` | `/api/prs` | ✅ | All personal records for user |
| `GET` | `/health` | — | Liveness probe |

---

## Agent — Self-Reflection Critique Loop

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

## Project Structure

```
fitforge/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, router registration
│   │   ├── config.py           # pydantic-settings (reads .env)
│   │   ├── models/             # User, WorkoutPlanRecord, WorkoutSession, ExerciseLog, PersonalRecord
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── routers/            # auth, workout, sessions (+ prs)
│   │   └── services/           # auth_service, ai_service (Groq), retrieval_service (RAG), agent_service (LangGraph)
│   ├── alembic/versions/       # 3 migrations: plans, sessions/logs, personal_records
│   ├── scripts/
│   │   ├── seed_demo.py        # Idempotent demo data seeder
│   │   ├── eval_agent.py       # Eval harness: /generate vs /generate-agent
│   │   └── eval_profiles.json  # 30 onboarding profiles (25 normal + 5 adversarial)
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/src/
│   ├── pages/                  # Home, Auth, Onboarding, WorkoutPlanPage, PlansHistory, Dashboard
│   ├── components/
│   │   ├── Navbar.jsx          # Shared responsive navbar (hamburger on mobile)
│   │   ├── LogWorkoutModal.jsx # Sets/reps/weight logging modal
│   │   ├── Toast.jsx           # Auto-dismiss notifications
│   │   ├── onboarding/         # 5-step form wizard
│   │   ├── workout/            # WorkoutPlan + DayCard
│   │   └── ui/                 # Button, ProgressBar
│   └── services/api.js         # Axios client + all API functions
│
└── docker-compose.yml
```

---

## License

MIT — built by [Meet Sutariya](https://github.com/meetsutariya4448) as a portfolio project.
