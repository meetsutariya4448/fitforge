# API reference

Moved out of the README to keep the front page short. The running app also
serves interactive docs at `http://localhost:8000/docs` (Swagger) and
`/redoc`, generated from the same FastAPI route definitions.

## Endpoints

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
