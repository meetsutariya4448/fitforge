# Project structure

Moved out of the README to keep the front page short.

## Layout

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
├── frontend/
│   ├── src/
│   │   ├── pages/              # Home, Auth, Onboarding, WorkoutPlanPage, PlansHistory, Dashboard
│   │   ├── components/
│   │   │   ├── Navbar.tsx      # Shared responsive navbar (hamburger on mobile)
│   │   │   ├── RequireAuth.tsx # Route guard; waits for the stored session
│   │   │   ├── LogWorkoutModal.tsx  # Sets/reps/weight logging modal
│   │   │   ├── Toast.tsx       # Auto-dismiss notifications
│   │   │   ├── onboarding/     # 5-step form wizard
│   │   │   ├── workout/        # WorkoutPlan + DayCard
│   │   │   └── ui/             # Button, ProgressBar
│   │   ├── contexts/AuthContext.tsx  # Single source of truth for auth state
│   │   ├── schemas/api.ts      # zod schemas — runtime validation + inferred types
│   │   └── services/api.ts     # Axios client, silent refresh, error normalisation
│   ├── e2e/                    # Playwright specs + the stubbed API they run against
│   └── scripts/                # check-api-contract.mjs (zod ↔ OpenAPI, runs in CI)
│
├── docs/usability-testing.md   # Task scripts and findings log
└── docker-compose.yml
```

Dashboard is still `.jsx`: the TypeScript migration is incremental by design,
and `allowJs` lets the remaining JavaScript coexist with the typed code.

---
