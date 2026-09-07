# ARCHIVE — Architecture

## Overview

ARCHIVE is a private, multi-user, cloud file-storage platform built as
two independently deployable services plus two data stores:

```
Browser (Next.js/TypeScript)
        |
       HTTPS
        |
FastAPI backend (Python) ----> PostgreSQL (metadata)
        |
        +---------------------> S3-compatible object storage (file bytes)
```

PostgreSQL is the single source of truth for *metadata*: who owns what,
folder hierarchy, filenames, sizes, checksums, timestamps, and audit
history. Object storage holds only opaque, encrypted-at-rest byte
blobs; it has no knowledge of folder structure or ownership beyond a
generated key.

The application server (FastAPI) is stateless with respect to file
content — it never writes uploaded bytes to local disk, and it does
not need to scale with total storage volume, only with request volume.

## Why presigned URLs

Routing large file uploads/downloads through the API server would mean:
- the server holding open connections proportional to upload duration
- doubling bandwidth costs (client → server → storage)
- the server becoming a single point of failure for all file transfer

Instead:

**Upload**
```
Browser -> FastAPI: "I want to upload X (name, type, size)"
FastAPI: authenticates, checks quota, creates a pending file row,
         generates a presigned PUT URL for a new opaque storage key
Browser -> Object storage: PUT file bytes directly, using that URL
Browser -> FastAPI: "Upload complete, here's the checksum"
FastAPI: verifies the object exists in storage, marks it completed
```

**Download**
```
Browser -> FastAPI: "Give me a download URL for file X"
FastAPI: verifies the requester owns file X
FastAPI -> Browser: a short-lived presigned GET URL
Browser -> Object storage: GET directly, using that URL
```

FastAPI is in the authorization path for every download but never
touches the bytes themselves.

## StorageService abstraction

All object-storage access goes through `app/services/storage.py`
(`StorageService`). No other module imports `boto3` or references a
provider-specific API. This is what makes ARCHIVE portable across AWS
S3, Backblaze B2, Cloudflare R2, Wasabi, and MinIO — switching
providers is a matter of changing `STORAGE_*` environment variables,
because all five speak the S3 API.

`StorageService` methods: `upload`, `delete`, `exists`,
`generate_upload_url`, `generate_download_url`, `copy`, `move`.

### Architectural decision: `STORAGE_PUBLIC_ENDPOINT`

In local Docker Compose, the backend reaches MinIO at `http://minio:9000`
(a Docker-network hostname the browser cannot resolve), but presigned
URLs are consumed by the browser and must point somewhere it *can*
reach, e.g. `http://localhost:9000`. `StorageService` therefore signs
URLs against an optional second, public-facing endpoint
(`STORAGE_PUBLIC_ENDPOINT`) while all other calls use the internal one.
In most production deployments (a single public S3-compatible
endpoint) this variable is left unset and both endpoints are the same.

## Storage object keys

Object keys are opaque and derived from the file's UUID
(`objects/<2-hex>/<2-hex>/<uuid>.bin`), never from the user-supplied
filename. This avoids directory-traversal risks, collisions, and
leaking filenames (which may contain PII) into storage-provider logs
or bucket listings. The mapping from file ID to storage key lives only
in PostgreSQL.

## Data model

- **users** — one row per account. `quota_bytes` lives here (not a
  separate plans table) so a per-user override is trivial today, and a
  `plans` table can be introduced later without migrating this column.
- **folders** — self-referential via `parent_id`, enabling arbitrary
  nesting. Soft-deleted via `deleted_at`.
- **files** — belongs to a user and optionally a folder. Has a
  `status` of `pending` (a presigned URL was issued but not yet
  confirmed) or `completed`. Soft-deleted via `deleted_at`.
- **audit_logs** — append-only record of security-relevant actions.

### Architectural decision: pending vs. completed file rows

A `File` row is created *before* the browser has actually uploaded
anything, at the moment a presigned URL is issued, with
`status="pending"`. This is necessary so quota checks
(`app/services/quota.py`) can account for uploads that are in flight,
preventing a burst of concurrent uploads from exceeding quota before
any of them individually completes. Pending rows are excluded from
normal file listings and search. A pending row whose upload never
completes is currently left in place (see "Known limitations" in the
README) rather than garbage-collected — acceptable for the MVP's scale,
revisit before that becomes a problem.

## Authorization model

Every folder/file endpoint resolves the resource through a single
"get-owned-or-404" helper (`_get_owned_folder_or_404`,
`_get_owned_file_or_404`) that filters by both the resource ID **and**
`user_id == current_user.id` in the same query. A resource ID that
exists but belongs to someone else returns 404, not 403 — this avoids
confirming to an attacker that the ID is valid at all.

The current user is derived exclusively from a server-verified,
httpOnly session cookie (see Authentication below) — never from any
`user_id` field a client could put in a request body, query string, or
path.

## Authentication

- Argon2id password hashing (via `argon2-cffi`), the current
  industry-recommended algorithm — no custom cryptography.
- Sessions are JWTs (user ID + expiry only, no sensitive claims)
  stored in an httpOnly, `SameSite=Lax` cookie; `Secure` is set
  whenever `APP_ENV=production`.
- Auth endpoints are rate-limited (`slowapi`) to slow down credential
  stuffing / brute force.
- The auth module is intentionally decoupled from the rest of the API
  (`app/api/deps.py::get_current_user` is the only integration point),
  so a dedicated identity provider (e.g. OAuth2/OIDC) can replace the
  current scheme later without touching folder/file/trash logic.

## Multi-user readiness

Every table that holds user data carries a `user_id` foreign key from
day one; there is no "single-user mode" shortcut anywhere in the
schema or API. The MVP ships with one real user, but the same code
path serves any number of accounts without modification.

## What's deliberately out of scope for v0.1

See the README's "Known limitations" and the original spec's "Future
Features" list. Notably: AI/semantic/vector search, file versioning,
sharing/public links, teams/organizations, billing, and client-side
("zero-knowledge") encryption. The storage and auth layers are
structured so none of these require a rearchitecture — e.g. a future
"Private Vault" mode can encrypt bytes in the browser before they ever
reach `generate_upload_url`, since `StorageService` never inspects
file contents.
