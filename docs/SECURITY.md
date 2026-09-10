# ARCHIVE — Security

## Reporting a vulnerability

This is an MVP without a public bug bounty program. If you find a
security issue while self-hosting ARCHIVE, please avoid filing it as a
public issue until you've had a chance to assess impact.

## What's implemented in v0.1

### Authentication
- Passwords hashed with Argon2id (`argon2-cffi`); plaintext passwords
  are never stored or logged.
- Sessions are JWTs in httpOnly cookies (`SameSite=Lax`, `Secure` in
  production), not accessible to JavaScript, mitigating token theft
  via XSS.
- Auth endpoints (`/api/auth/register`, `/api/auth/login`) are rate
  limited per-IP via `slowapi`.
- Login and registration return generic error messages that do not
  confirm whether a given email is registered.

### Authorization / data isolation
- Every folder and file query is scoped by `user_id` at the database
  level — there is no code path that fetches a resource by ID alone.
- Cross-user access attempts return `404`, not `403`, so existence of
  another user's resource is never confirmed.
- See `backend/tests/test_isolation.py` for automated proof: User A
  cannot read, rename, delete, move files into, or obtain a download
  URL for User B's resources, and forged `user_id` fields in request
  bodies are ignored (the session is always the source of truth).

### Transport & headers
- Production deployments must terminate HTTPS (at a load balancer,
  reverse proxy, or the hosting platform) — ARCHIVE assumes TLS is
  present in front of it in production.
- Responses set `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
  a restrictive `Permissions-Policy`, and `Strict-Transport-Security`
  (in production).
- CORS is restricted to the configured `CORS_ORIGINS` — not `*`.

### Input validation
- All request bodies are validated by Pydantic schemas; the API never
  accepts or reflects raw SQLAlchemy models.
- SQL is issued exclusively through SQLAlchemy's query builder
  (parameterized), which prevents SQL injection by construction — no
  raw string-interpolated SQL exists in the codebase.
- Upload MIME type is checked against an explicit allow-list and file
  size against a configured ceiling before a presigned URL is even
  issued.
- The frontend never uses `dangerouslySetInnerHTML` or otherwise
  injects unsanitized content into the DOM, limiting XSS surface.

### Object storage
- Storage keys are opaque UUID-derived paths, never user-supplied
  filenames — this prevents path traversal and avoids leaking
  potentially sensitive filenames into storage-provider logs.
- Storage credentials exist only in backend environment variables and
  are never sent to the browser. The browser only ever receives
  short-lived, scoped presigned URLs.
- Presigned upload URLs expire after
  `STORAGE_PRESIGNED_UPLOAD_EXPIRE_SECONDS` (default 10 minutes);
  download URLs after `STORAGE_PRESIGNED_DOWNLOAD_EXPIRE_SECONDS`
  (default 5 minutes).

### Secrets
- All secrets (`JWT_SECRET`, storage credentials, database URL) are
  read from environment variables via `pydantic-settings`; none are
  hardcoded, and `.env` is git-ignored.
- `.env.example` documents required variables without real values.

### Logging
- Structured logs cover authentication events, upload/storage
  failures, and unhandled exceptions.
- Logs never include passwords, session tokens, storage credentials,
  or file contents. The global exception handler
  (`app/main.py::unhandled_exception_handler`) ensures stack traces
  and internal error detail are never returned to the client, only
  logged server-side.

### Auditing
- `audit_logs` records `LOGIN`, `LOGOUT`, `UPLOAD`, `DOWNLOAD`,
  `DELETE`, `RESTORE`, `PERMANENT_DELETE`, `CREATE_FOLDER`, and
  `RENAME_FOLDER` events with user ID, IP, user agent, and timestamp.

## Explicitly NOT implemented in v0.1 (do not assume otherwise)

- **No end-to-end / zero-knowledge encryption.** Files are encrypted
  at rest by the storage provider (standard S3-compatible
  server-side encryption) and in transit via HTTPS, but ARCHIVE itself
  can technically access file bytes. Do not describe this version as
  "zero-knowledge" or "end-to-end encrypted" — that will only become
  true if/when a client-side "Private Vault" encryption mode is built.
- **No malware/antivirus scanning.** MIME-type and size validation are
  not a substitute for content scanning. The upload pipeline is
  structured so a scanning step could be inserted between "upload
  confirmed" and "visible to the user" later.
- **No CSRF token scheme beyond `SameSite=Lax` cookies.** `SameSite=Lax`
  blocks the common cross-site POST forgery vectors for this app's
  cookie-based auth; a dedicated CSRF token would be needed if cookies
  are ever changed to `SameSite=None`.
- **No enterprise SSO, granular permissions, or sharing.** Every
  resource has exactly one owner in v0.1.

## Dependency hygiene

Run `pip list --outdated` (backend) and `npm outdated` (frontend)
periodically, and keep an eye on GitHub's Dependabot alerts once this
repository is pushed to GitHub.
