# FitForge — AI Fitness Platform

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
- Full JWT-authenticated accounts with 24-hour tokens

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

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | Random secret for signing JWTs |
| `GROQ_API_KEY` | ✅ | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | | Model ID (default: `llama-3.3-70b-versatile`) |
| `APP_ENV` | | `development` or `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | JWT lifetime in minutes (default: `1440`) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | ✅ (production) | Backend URL e.g. `https://your-app.onrender.com` |

---

## API Reference

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/api/auth/register` | — | Create account, returns JWT |
| `POST` | `/api/auth/login` | — | Login, returns JWT |
| `GET` | `/api/auth/me` | ✅ | Current user profile |
| `POST` | `/api/workout/generate` | ✅ | AI plan generation + save to DB |
| `GET` | `/api/workout/history` | ✅ | All saved plans for user |
| `POST` | `/api/sessions` | ✅ | Log workout session (auto-upserts PRs) |
| `GET` | `/api/sessions` | ✅ | All sessions for user |
| `GET` | `/api/sessions/exercise/{name}` | ✅ | Per-exercise strength trend data |
| `GET` | `/api/sessions/{id}` | ✅ | Single session by ID |
| `GET` | `/api/prs` | ✅ | All personal records for user |
| `GET` | `/health` | — | Liveness probe |

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
│   │   └── services/           # auth_service (JWT/bcrypt), claude_service (Groq)
│   ├── alembic/versions/       # 3 migrations: plans, sessions/logs, personal_records
│   ├── scripts/seed_demo.py    # Idempotent demo data seeder
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
