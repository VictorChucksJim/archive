# ARCHIVE

A private, multi-user digital archive / cloud file-storage platform —
a professional, self-hostable alternative to Google Drive or OneDrive,
built around data ownership, privacy, and portability between storage
providers.

This is **v0.1**, an MVP. See `docs/ARCHITECTURE.md` for design
rationale, `docs/SECURITY.md` for what is and isn't hardened yet, and
`docs/API.md` for the API reference.

## What works today

Register → log in → dashboard → create nested folders → upload files
(directly to object storage via presigned URLs, with progress) →
search → download → rename → delete → Trash → restore → permanently
delete. Storage quota (1 TB/user by default) is enforced on every
upload. Every file is SHA-256 checksummed. Every folder/file is
strictly isolated per user.

## Architecture

```
Next.js (TypeScript, Tailwind) → FastAPI (Python) → PostgreSQL (metadata)
                                                   → S3-compatible storage (file bytes)
```

Object storage works with AWS S3, Backblaze B2, Cloudflare R2, Wasabi,
or MinIO — see `STORAGE_*` variables below. See
`docs/ARCHITECTURE.md` for the full explanation of the presigned-URL
upload/download flow and the `StorageService` abstraction.

## Prerequisites

- Docker and Docker Compose (recommended path), **or**
- Python 3.12+, Node.js 20+, a PostgreSQL 16 instance, and an
  S3-compatible storage bucket, for running services individually.

## Quick start (Docker Compose)

```bash
cp .env.example .env
# edit .env if you want non-default values; the defaults work out of
# the box with the bundled Postgres + MinIO containers.

docker compose up --build
```

This starts:
- `postgres` — metadata database
- `minio` (+ `minio-init`) — local S3-compatible storage for development, with the `archive-dev` bucket created automatically
- `backend` — FastAPI, running Alembic migrations on startup, on `:8000`
- `frontend` — Next.js, on `:3000`

Then open **http://localhost:3000**, register an account, and use the
app. MinIO's web console (for inspecting stored objects) is at
**http://localhost:9001** (`minioadmin` / `minioadmin`).

## Local development without Docker

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point DATABASE_URL / STORAGE_* at your own Postgres + S3-compatible
# bucket (see .env.example), then:
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` (in `frontend/.env.local` or your shell) to
point at the backend, e.g. `http://localhost:8000`.

## Database migrations

Migrations are managed with Alembic from inside `backend/`:

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after changing app/models/models.py
alembic revision --autogenerate -m "describe the change"

# Roll back one migration
alembic downgrade -1
```

## Object storage configuration

Set these (via `.env` or your platform's secret manager) to point at
any S3-compatible provider — no code changes required:

| Variable | Example (AWS S3) | Example (MinIO, local) |
|---|---|---|
| `STORAGE_ENDPOINT` | `https://s3.us-east-1.amazonaws.com` | `http://minio:9000` |
| `STORAGE_PUBLIC_ENDPOINT` | *(usually unset)* | `http://localhost:9000` |
| `STORAGE_REGION` | `us-east-1` | `us-east-1` |
| `STORAGE_BUCKET` | `my-archive-prod` | `archive-dev` |
| `STORAGE_ACCESS_KEY` | IAM access key | `minioadmin` |
| `STORAGE_SECRET_KEY` | IAM secret key | `minioadmin` |
| `STORAGE_USE_PATH_STYLE` | `false` (most AWS setups) | `true` |

`STORAGE_PUBLIC_ENDPOINT` is only needed when the backend and browser
must reach storage via different hostnames (this is why local Docker
Compose needs it — see `docs/ARCHITECTURE.md`).

For Backblaze B2, Cloudflare R2, or Wasabi: use each provider's
S3-compatible endpoint URL and credentials in the same variables.

## Running tests

### Backend (unit, integration, and security/isolation tests)

Requires a disposable PostgreSQL database (tests use real Postgres
because the schema relies on native UUID columns):

```bash
cd backend
export TEST_DATABASE_URL=postgresql+psycopg2://archive:archive@localhost:5432/archive_test
pytest -v
```

This includes `tests/test_isolation.py`, which specifically proves
User A cannot access User B's files, folders, or download URLs.

### Frontend lint / type-check / build

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

### End-to-end (Playwright)

Requires the full stack running (e.g. via `docker compose up`) at
`http://localhost:3000`:

```bash
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

This automates the complete workflow: register → login → dashboard →
create folder → upload → verify → download → rename → delete → Trash
→ restore → verify → permanently delete → verify gone. Uses a
generated throwaway test PDF and a randomly generated email — never
real documents or credentials.

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR: backend tests
(against a Postgres service container), frontend lint + type-check +
build, and a final Docker image build for both services. A broken
build fails the pipeline.

## Production deployment

1. Provision PostgreSQL and an S3-compatible bucket (any provider
   listed above).
2. Set all variables from `.env.example` with real values —
   especially a long random `JWT_SECRET`
   (`python -c "import secrets; print(secrets.token_urlsafe(64))"`)
   and real storage/database credentials. Set `APP_ENV=production`.
3. Put both `frontend` and `backend` behind HTTPS — a reverse proxy
   (nginx, Caddy) or your hosting platform's TLS termination. ARCHIVE
   does not terminate TLS itself.
4. Build and run the two Docker images (`backend/Dockerfile`,
   `frontend/Dockerfile`), or deploy to your platform of choice (ECS,
   Cloud Run, Fly.io, Render, a VM with Docker Compose, etc.).
   `docker-entrypoint.sh` runs `alembic upgrade head` before starting
   the API, so migrations apply automatically on deploy.
5. Set `CORS_ORIGINS` to your real frontend origin(s) only.
6. Point `NEXT_PUBLIC_API_URL` at your real backend origin at build
   time.

## Known limitations (v0.1)

- No client-side ("zero-knowledge"/end-to-end) encryption yet — see
  `docs/SECURITY.md` for exactly what encryption is and isn't in
  place today, and `docs/ARCHITECTURE.md` for how a future "Private
  Vault" mode would fit in without a rearchitecture.
- No malware scanning on uploads (MIME/size validation only).
- No file versioning, sharing/public links, teams, billing, or SSO —
  all explicitly out of scope for this MVP (see the project spec's
  "Future Features" list).
- Search is basic `ILIKE` filename/folder-name matching — no
  AI/semantic/vector search.
- A presigned upload that a browser never actually completes leaves a
  `pending` file row and reserved quota behind; there's no background
  job yet to garbage-collect abandoned uploads.
- Per-file preview is implemented for common image formats and PDFs
  only; everything else shows "No preview available" with a download
  link.

## Project structure

```
archive/
├── frontend/         Next.js (TypeScript, Tailwind) app
├── backend/          FastAPI (Python) app + Alembic migrations + tests
├── docs/             ARCHITECTURE.md, SECURITY.md, API.md
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml
```
