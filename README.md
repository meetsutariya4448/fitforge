# FitForge

**FitForge** is a full-stack AI fitness platform that generates personalised weekly workout plans in seconds. Users answer five questions about their goals, fitness level, and available equipment, and the Groq-powered AI produces a structured, day-by-day training plan tailored to them. Plans are saved to a PostgreSQL database so users can revisit any past plan, log completed workouts with sets, reps, and weight, and track their progress through an interactive dashboard with charts.

🔗 **Live demo:** [https://fitforge-six.vercel.app](https://fitforge-six.vercel.app)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, React Router v6, Tailwind CSS, Framer Motion, Recharts |
| Backend | FastAPI, Python 3.11, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL |
| AI | Groq API — Llama 3.3 70b Versatile |
| Auth | JWT (python-jose, HS256), bcrypt password hashing |
| Deployment | Backend → Render · Frontend → Vercel |

---

## Features

- **AI Plan Generation** — Describe your goals and equipment; receive a complete weekly workout plan with exercises, sets, reps, rest periods, warmup and cooldown notes, and coaching tips
- **Plan History** — Every generated plan is saved to your account so you can revisit or replay any past plan without regenerating
- **Workout Logging** — Log each training day directly from the plan view: input actual sets, reps, and weight per exercise
- **Progress Dashboard** — Four stat cards (total sessions, total volume, sessions this week, most trained exercise) plus three interactive charts — volume over time (line), weekly consistency (bar), and top exercises by frequency (horizontal bar)
- **JWT Authentication** — Secure register/login flow; token persists in `localStorage` and is attached automatically to every API request
- **Responsive Design** — Dark-themed UI built with Tailwind CSS, fully usable on mobile and desktop

---

## Screenshots

> _Add screenshots or a short GIF here._

| Onboarding | Plan View | Dashboard |
|------------|-----------|-----------|
| _(screenshot)_ | _(screenshot)_ | _(screenshot)_ |

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (running locally, or use Docker)

---

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and fill in your values
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the dev server
uvicorn app.main:app --reload --port 8000
```

API will be available at `http://localhost:8000`.  
Interactive docs at `http://localhost:8000/docs`.

---

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy env file and set the backend URL
cp .env.example .env
# For local dev the Vite proxy handles /api/* automatically —
# you can leave VITE_API_BASE_URL blank or set it to http://localhost:8000

# Start the dev server
npm run dev
```

App will be available at `http://localhost:5173`.

---

### Docker (optional)

Spin up Postgres + the backend together:

```bash
docker compose up --build
```

The backend will be available at `http://localhost:8000`.  
Run the frontend separately with `npm run dev` inside `/frontend`.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string, e.g. `postgresql://user:pass@localhost:5432/fitforge` |
| `SECRET_KEY` | ✅ | Random string used to sign JWTs — keep secret in production |
| `GROQ_API_KEY` | ✅ | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | | Groq model ID (default: `llama-3.3-70b-versatile`) |
| `APP_ENV` | | `development` or `production` (default: `development`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | JWT lifetime in minutes (default: `1440` — 24 hours) |
| `ALGORITHM` | | JWT signing algorithm (default: `HS256`) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | ✅ (production) | Full URL of the backend, e.g. `https://your-app.onrender.com`. Not needed locally — the Vite dev proxy handles it. |

---

## Project Structure

```
fitforge/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, router registration
│   │   ├── config.py        # pydantic-settings (reads .env)
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   ├── models/          # ORM models (users, workout_plans, sessions)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── routers/         # auth, workout, sessions endpoints
│   │   └── services/        # auth_service (JWT/bcrypt), claude_service (Groq)
│   ├── alembic/             # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── pages/           # Home, Auth, Onboarding, WorkoutPlanPage, PlansHistory, Dashboard
│       ├── components/      # Button, Toast, LogWorkoutModal, DayCard, OnboardingForm, …
│       └── services/
│           └── api.js       # Axios client + all API functions
│
└── docker-compose.yml
```

---

## API Endpoints

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/api/auth/register` | — | Create account, returns JWT |
| `POST` | `/api/auth/login` | — | Login, returns JWT |
| `GET` | `/api/auth/me` | ✅ | Get current user profile |
| `POST` | `/api/workout/generate` | ✅ | Generate AI workout plan + save to DB |
| `GET` | `/api/workout/history` | ✅ | Get all saved plans for current user |
| `POST` | `/api/sessions` | ✅ | Log a completed workout session |
| `GET` | `/api/sessions` | ✅ | Get all sessions for current user |
| `GET` | `/api/sessions/{id}` | ✅ | Get one session by ID |
| `GET` | `/health` | — | Liveness probe |

---

## License

MIT
