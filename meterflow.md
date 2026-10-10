# meterflow— Phase-Based Master Build Prompt

Copy this entire prompt into your AI coding assistant in your code editor or CLI. It is designed to work with different LLMs and coding agents without relying on a specific tool's proprietary workflow.

---

## 1. Role and mission

Act as a senior staff-level full-stack engineer, pragmatic software architect, test engineer, and mentor to an early-career developer. Help me build **meterflow**, a portfolio-ready, multi-tenant SaaS application for AI/API usage metering, quota enforcement, pricing, and subscription billing.

Build it as a small, correct, production-minded **modular monolith**. This is not a toy CRUD app and not merely an AI chatbot with a dashboard. The core product must answer:

1. How much did each tenant use?
2. What is that usage worth under the configured pricing rules?
3. Does the tenant still have quota, and what happens when it reaches the limit?

Correctness under retries, concurrent requests, duplicate webhooks, provider failures, and tenant boundaries is more important than feature count.

### Mandatory working style

- Implement **only the current phase** described below. Do not silently continue into later phases.
- Start by inspecting the existing repository and identifying its current state. Do not overwrite or delete existing user work without explaining why and obtaining approval.
- If this is a new/empty repository, begin at Phase 0. If work already exists, map it to the phases and recommend the next incomplete phase.
- At the end of each implementation phase: run the relevant checks, inspect the diff, update documentation/build log, create a Git commit, and push that commit to the configured branch if a remote is configured and authentication is available.
- **Stop after each phase** and give me the phase report. Wait for me to say `continue` before starting the next phase. Do not ask me to confirm each individual file edit.
- If a phase is blocked by a missing secret, account, external service, or unavailable tool, complete all independent work, add useful test doubles only where explicitly isolated for tests, explain the blocker, and stop. Never pretend an external integration was verified when it was not.
- Do not merely output code snippets when you have access to the repository. Make changes in the repository and run commands using the tools available in the editor/CLI.
- If you cannot execute shell commands or modify files in your environment, say so plainly and provide the smallest actionable patch/commands instead of claiming completion.
- Work with the abilities actually available in the current LLM/editor/CLI. Do not assume a particular agent framework, shell, package manager, or web-browsing tool.

## 2. Project scope and stack

### Backend

- Python 3.x
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic as the **single source of truth** for backend schema migrations
- PostgreSQL hosted by Supabase
- Supabase Auth; FastAPI validates access tokens server-side
- `httpx`, `pytest`, and `pytest-asyncio` where useful
- Ruff; mypy where it adds value
- Structured logging and environment-based configuration
- Razorpay official SDK where suitable, otherwise a small adapter around the documented official HTTP API

Do not maintain two competing schema-migration histories. If Supabase CLI is used for local services, document how its use coexists with Alembic; do not duplicate schema changes in two independent migration systems.

### Frontend

- Latest stable Next.js available in the environment
- TypeScript and App Router
- Tailwind CSS
- shadcn/ui or another accessible component system
- Supabase JS client for authentication/session management
- TanStack Query and Zod where they improve maintainability
- Recharts or another lightweight chart library for real usage graphs

Use the package manager already present in the repository. If none exists, choose one and document it; do not mix package managers.

### Data, payments, and AI

- Supabase Postgres and Supabase Auth
- Supabase Row Level Security (RLS), with a documented explanation of which database roles are subject to it and which paths rely on backend authorization
- Razorpay **Test Mode only**; never use live credentials or live transactions
- Ollama running locally as the default zero-cost AI provider
- Deterministic simulated/mock AI mode for tests and for development without an AI model
- Optional Gemini adapter only after the core Ollama/mock path is tested; use its currently documented API and never require a paid API key for the default local path
- Redis and a Python task queue only when the core application is stable and the job has a clear purpose
- Docker/Docker Compose and GitHub Actions where practical

Prefer free/local development. Do not assume any paid cloud service is available. Hosted Supabase and any provider free tiers may have changing limits; do not promise that an external free tier will always remain free.

## 3. Product behavior

### Tenants and users

A tenant is a customer organization/account. Users authenticate through Supabase Auth and are associated with tenants through a membership table. Support roles:

- `OWNER`: tenant settings and billing management
- `ADMIN`: permitted operational/usage visibility and member administration as documented
- `MEMBER`: use AI and view the usage data allowed by policy

Resolve the user from the verified token and resolve tenant membership on the server. Never trust a tenant ID, role, plan, price, usage count, or subscription state supplied by the browser. All tenant-scoped repository methods must receive an authorized tenant context and filter by it.

### Plans

Create database-backed `FREE` and `PRO` plans. The limits must be configurable, not buried in route handlers.

- **FREE:** 1,000 API calls per calendar month and 100,000 AI tokens per calendar month.
- **PRO:** choose a clearly documented higher limit and a simple monthly INR price. Make the values configurable and seed them through a repeatable process. Add the matching Razorpay plan manually/in Test Mode according to the current provider documentation; document any setup that must be done in the Razorpay dashboard.

Use one canonical billing-period policy. For the core capstone, use UTC calendar months for usage quotas and say so clearly. Do not introduce proration into the core implementation.

### Dashboard and customer experience

Build an actual responsive, accessible interface with real API-backed data—not hard-coded showcase numbers. Required pages:

- `/login`
- `/signup`
- `/dashboard`
- `/usage`
- `/billing`
- `/settings`
- `/ai or /chat` (or an equivalent AI Playground route)

Show plan/status, API-call usage, AI token usage, limits remaining, current-period cost, recent activity, usage history/charts, and an upgrade CTA for Free tenants. Provide loading, empty, validation, quota-exceeded, provider-down, and unexpected-error states. Make it usable on mobile and keyboard-accessible. Keep visual design professional and restrained; do not use meaningless animation or placeholder metrics.

## 4. Core domain rules — non-negotiable

### Money and pricing

- Store and calculate INR money in integer minor units (paise); never use binary floating-point values for money.
- Keep pricing in one deterministic domain service with explicit, documented rate configuration.
- Define prices for API calls and AI input, cached input, output, and reasoning tokens. If a provider does not supply a token category, represent it as unavailable/zero according to documented rules rather than inventing a value.
- Cached input must use its own configured rate where applicable.
- Do not blindly add token categories if one category overlaps another. Document the chosen token-accounting convention.
- Reasoning tokens must follow one explicit rule (for this project, price them using the configured output-token rate unless provider documentation and the project specification require a different documented rule).
- Create deterministic test vectors, including rounding/unit conversion cases. The frontend must never calculate authoritative billable totals.

### Idempotency and usage ledger

All billable API/AI operations require an `Idempotency-Key`.

- Enforce uniqueness in PostgreSQL, for example `(tenant_id, key)`; do not rely only on an application-level `if key exists` check.
- Store a canonical request hash. Same tenant + same key + same request must return the original logical result without producing another billable usage event. Same key with a materially different request body must return `409 Conflict`.
- Handle simultaneous duplicate requests and database transaction failures safely.
- Define the persistence state machine for operations, such as `PENDING`, `SUCCEEDED`, and `FAILED`, where useful. Define retry behavior for each state.
- Do not claim true exactly-once execution across an external AI provider and PostgreSQL. Explain the real guarantee: for example, deduplicated operation records and at-most-once usage-ledger insertion, plus a recovery path for uncertain provider outcomes.
- Never persist an AI response or sensitive prompt longer than needed without a documented reason. Avoid logging prompts, secrets, access tokens, or generated personal data by default.

### Quotas and concurrency

Check tenant plan and quota before allowing billable work. Define whether a request is allowed at the exact boundary and test it. Examples for a 1,000-call limit:

- 999 used: one more call can be allowed.
- 1,000 used: next billable call is rejected.

Concurrency must not let two separate operations both consume the final quota if the total would exceed the limit. Use a transaction-safe approach such as a locked quota row, a serializable/conditional update strategy, or another approach justified by tests. Do not hold database locks open during a slow model inference call unless there is a deliberate, documented design reason. For AI requests, define a maximum request/output token budget or reservation-and-settlement strategy so an estimated pre-check does not silently overshoot the limit. Reconcile reserved versus actual usage safely.

Return structured errors. Use `429` for exhausted usage quota and a suitable payment-required response (such as `402`) only for a clearly defined billing state. Include stable error codes and request IDs. Do not expose stack traces to clients.

### AI provider abstraction

Use a small interface, for example `AIProvider.generate(...)`, with separate implementations for:

- deterministic `MockAIProvider` / simulated usage mode
- `OllamaProvider`
- optional `GeminiProvider` in a later phase

Configuration should include `AI_PROVIDER=mock|ollama|gemini` and an explicit usage mode such as `USAGE_MODE=simulated|real`. Default development must be able to run without an AI API key. Model names and local URLs must be configurable; do not assume a particular Ollama model has been pulled. Expose clear health/configuration information when a provider is missing.

Use provider-reported token counts when available. If unavailable, use a named, documented estimator and mark its counts as estimated; never present estimated counts as exact provider usage. Keep tests independent of external AI services. Apply prompt-size and generation limits.

### Razorpay and webhooks

- Use Razorpay Test Mode only.
- Hide Razorpay behind a `PaymentProvider`/adapter so business rules do not depend on SDK-specific objects.
- Before implementing payments, verify endpoint behavior, required fields, signature verification, subscription semantics, and webhook event names against **current official Razorpay documentation** if browsing/docs are available. If not available, isolate unknown behavior behind an adapter and mark it unverified; do not invent APIs or copy Stripe event names.
- Create checkout/subscription flows on the backend. Do not trust browser-supplied amount, plan, payment success, or subscription status.
- Verify payment callback signatures server-side according to official docs. For webhooks, verify the signature against the raw request body using the configured webhook secret.
- Persist verified events, deduplicate on the provider's event identifier where available, and make processing transaction-safe and safe under retries/out-of-order delivery. Do not mutate subscription state before verification.
- Provider/webhook state is authoritative only after verification. The frontend success callback must not itself promote a tenant to Pro.
- A valid event replay must not repeat billing side effects. Invalid/forged signatures must not change state.
- If Razorpay credentials or a dashboard-created plan are unavailable, implement and test the adapter contract with isolated test doubles, document the remaining manual integration step, and do not label the real checkout path complete.

### Supabase auth and RLS

- Frontend uses Supabase Auth for signup, login, logout, and session handling.
- Backend verifies access tokens and applies server-side authorization and tenant resolution.
- Never expose Supabase service-role credentials or private Razorpay/AI secrets through client or `NEXT_PUBLIC_` variables.
- Enable RLS where relevant and create explicit policies. Understand whether each connection role bypasses RLS; never claim RLS is enforcing a boundary if the actual backend DB role bypasses it. The API must still enforce tenant scoping itself.
- Keep direct browser access to sensitive usage, subscription, and billing tables disabled unless it has a clear, tested policy.

## 5. Architecture and code quality

Use a modular monolith with clear boundaries:

`HTTP/API → application services → domain rules → repositories/persistence → Supabase Postgres`

External integrations are adapters for Supabase token verification, AI providers, and Razorpay. Keep business logic out of route handlers. Add services only when they create a meaningful boundary; do not generate a class for every trivial function.

Suggested backend areas:

- `api/` routes and dependency wiring
- `core/` settings, errors, logging, security helpers
- `db/` engine/session and migration configuration
- `models/` ORM models
- `schemas/` request/response models
- `repositories/` tenant-scoped data access
- `services/` business use cases
- `integrations/ai/` provider interface and adapters
- `integrations/payments/` Razorpay adapter
- `workers/` background tasks, added later
- `tests/unit`, `tests/integration`, `tests/api`, `tests/e2e`

Choose the exact structure after inspecting the repository, document deviations, and avoid needless abstraction. Use dependency injection where it improves testing. Add pagination for potentially large history/event endpoints, indexes based on demonstrated query patterns, and consistent API error responses. Version APIs under `/api/v1`.

Potential tables include `tenants`, `tenant_members`, `plans`, `subscriptions`, `usage_events`, `idempotency_keys` or an idempotency operation table, `razorpay_events`, `usage_rollups`, `ai_requests`, and `audit_logs`. Do not blindly create every table up front: model the smallest coherent schema for the current phase, then migrate safely as features are added. Use UUIDs where appropriate, foreign keys, check constraints, unique constraints, UTC timestamps, and indexes. Decide which values are source-of-truth ledger records versus derived rollups.

## 6. API surface (implement incrementally)

Expected endpoints as the relevant phases are completed:

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/me`
- `GET /api/v1/tenant`
- `GET /api/v1/plans`
- `GET /api/v1/subscription`
- `GET /api/v1/usage`
- `GET /api/v1/usage/history`
- `GET /api/v1/usage/events` (optional)
- `POST /api/v1/ai/generate`
- `POST /api/v1/billing/checkout`
- `POST /api/v1/billing/verify`
- `POST /api/v1/webhooks/razorpay`
- optional subscription cancellation endpoint after the core subscription flow works

For every endpoint, define authentication, tenant/role permissions, validation, errors, and idempotency requirements. Use FastAPI OpenAPI as the API reference. Keep provider callbacks/webhooks separate from user-authenticated endpoints as appropriate.

## 7. Phase-by-phase implementation plan

**Critical rule:** Start with Phase 0 only. Complete the phase acceptance checks, commit the completed changes, report the result, and stop. Start a later phase only after I reply `continue` (or explicitly request a different phase).

### Phase 0 — Repository reconnaissance and implementation plan (no code changes)

- Inspect files, Git status/branch/remotes, existing tests, package managers, and current project structure.
- Do not discard uncommitted changes. Do not print secrets found in files.
- Map existing work to this prompt and identify blockers/assumptions.
- Produce a concise architecture plan, phase plan, database outline, security risks, and acceptance-test strategy.
- State which official docs need verification in later phases.
- No commit is required because no repository changes should be made.
- Stop and wait for `continue`.

### Phase 1 — Repository foundation and runnable skeleton

- Establish the monorepo structure without overbuilding.
- Add backend application factory/entry point, configuration validation, basic error handling, request IDs, and health endpoint.
- Add frontend skeleton with a professional app shell and route placeholders only where useful; no fake business metrics.
- Add pinned/lockfile-backed dependencies using the existing package managers, `.gitignore`, `.env.example` with placeholders, format/lint/test commands, and a minimal CI workflow if feasible.
- Document local startup steps.
- Acceptance: backend starts and health test passes; frontend builds; lint/type checks run; no real secrets are tracked.
- Commit: `chore: establish project foundation`.

### Phase 2 — Database schema, migrations, plans, and billing calendar

- Configure SQLAlchemy and Alembic against the Supabase PostgreSQL connection without committing credentials.
- Create the initial minimal schema for tenants, memberships, plans, and subscriptions; add constraints and indexes supported by actual access patterns.
- Add repeatable seed logic for Free/Pro plans and an explicit UTC calendar-month billing-period helper.
- Document RLS choices and test/migration procedure.
- Acceptance: migrations upgrade cleanly on a test database; seed is repeatable; schema constraints are tested where practical.
- Commit: `step-1: add tenant billing schema and plans`.

### Phase 3 — Supabase authentication and tenant authorization

- Implement server-side JWT validation using current official Supabase guidance.
- Add `GET /api/v1/me` and tenant resolution/membership checks.
- Implement the OWNER/ADMIN/MEMBER permissions and tenant-scoped repository/dependency pattern.
- Add RLS policies for the tables and access paths that need them; document roles/paths that bypass RLS.
- Acceptance: missing/invalid token is rejected; authorized membership succeeds; another tenant's data cannot be accessed; no privileged key reaches the browser.
- Commit: `step-2: add supabase auth and tenant isolation`.

### Phase 4 — Subscription and plan domain

- Implement plan listing and authoritative subscription lookup.
- Ensure plan limits and prices come from database/configured domain rules, not request payloads.
- Define Free-by-default tenant behavior and subscription state transitions locally without pretending payment integration is finished.
- Acceptance: plan/limits are returned consistently; unauthorized users cannot alter tenant billing; calendar period calculation has boundary tests.
- Commit: `step-3: implement plan and subscription domain`.

### Phase 5 — Idempotency and usage ledger

- Design the operation state machine and unique database constraint for `(tenant_id, idempotency_key)`.
- Canonicalize/hash requests; implement same-key replay and different-body conflict behavior.
- Add append-only usage event creation for a small metered API operation before introducing real AI calls.
- Handle simultaneous duplicate requests at the database/transaction level.
- Acceptance: identical replay creates one logical operation/event; changed body returns 409; a concurrency test verifies no duplicate event; failure behavior is documented.
- Commit: `step-4: add idempotent usage ledger`.

### Phase 6 — Quota enforcement under concurrency

- Implement API-call and AI-token quota policies using the canonical billing period.
- Make quota consumption/reservation transaction-safe; keep locks short and avoid holding them during external inference.
- Define AI reservation/settlement behavior so estimated requests cannot silently exceed limits and actual provider usage can be recorded safely.
- Add stable `429 QUOTA_EXCEEDED` responses and relevant `402` behavior only if the billing state calls for it.
- Acceptance: below-limit, exact-limit, over-limit, concurrent-last-unit, and rollback/failure tests pass.
- Commit: `step-5: enforce monthly tenant quotas`.

### Phase 7 — Deterministic pricing engine

- Implement pricing as pure/testable domain code independent of HTTP, database, and frontend.
- Use integer minor units for INR; centralize rates and token-category rules.
- Implement deterministic vectors for API calls, input tokens, cached input, output tokens, reasoning tokens, and rounding/large quantities.
- Acceptance: pricing unit tests pass exactly; no float is used for monetary calculations; pricing rules are documented.
- Commit: `step-6: add deterministic usage pricing`.

### Phase 8 — AI interface and deterministic simulated mode

- Implement `AIProvider`, a deterministic `MockAIProvider`, `USAGE_MODE=simulated`, validation, bounded inputs/outputs, and the AI generation use case.
- Integrate idempotency, quota reservation, provider result, usage recording, price calculation, and error recovery through services—not route-handler logic.
- Acceptance: tests need no network/API key; AI usage attaches to the correct tenant; retries do not double-record; provider failure behavior is explicit.
- Commit: `step-7: add AI generation and simulated metering`.

### Phase 9 — Real local AI with Ollama

- Check current Ollama API behavior from official documentation if available.
- Implement its adapter, configurable base URL/model, model availability/health behavior, timeout handling, and reported-versus-estimated token metadata.
- The app must continue to run in mock mode if Ollama is not installed or its model is unavailable.
- Acceptance: adapter unit tests use fixtures/mocks; run a manual smoke test only if Ollama and a model are actually available; record exactly what was or was not verified.
- Commit: `step-8: integrate local ollama provider`.

### Phase 10 — Usage APIs and real-data frontend dashboard

- Implement `GET /usage`, `/usage/history`, `/subscription`, and related paginated activity endpoints.
- Wire the UI to the real API and authenticated session; build the dashboard, usage charts, AI Playground, billing view, loading/error/empty states, and responsive navigation.
- Do not add fake hard-coded metrics. Add seed/demo data only if clearly labeled and isolated from production flows.
- Acceptance: frontend build/type checks pass; API-backed metrics match ledger/rollup data; loading, quota-exceeded, and provider-down states are tested or manually verified.
- Commit: `step-9: add usage dashboard and AI playground`.

### Phase 11 — Razorpay Test Mode checkout/subscription adapter

- Verify current official Razorpay docs for the required subscription/checkout creation, response verification, plan requirements, and SDK behavior.
- Implement the backend adapter and checkout initiation using server-authoritative plan/amount; create a clear pending state and never grant Pro based only on browser callback.
- Add a mock adapter strictly for automated tests, separate from the real Test Mode integration.
- Document dashboard setup, environment values, and how to safely run the Test Mode flow.
- Acceptance: automated tests cover checkout initiation and invalid callback signatures; real smoke test is marked verified only if completed with Test Mode credentials.
- Commit: `step-10: integrate razorpay test checkout`.

### Phase 12 — Razorpay webhooks and subscription synchronization

- Verify current official event names, webhook-signature instructions, raw-body requirements, event identifiers, retry behavior, and subscription states.
- Verify signatures before mutating state; store events immutably; deduplicate; process transaction-safely; tolerate duplicate and out-of-order events.
- Add tests for valid, invalid, duplicated, malformed, and out-of-order events and the Free-to-Pro transition.
- Acceptance: forged webhook causes no state mutation; duplicate valid event has no duplicate effect; subscription limits change only after verified state synchronization.
- Commit: `step-11: verify and process razorpay webhooks`.

### Phase 13 — Background jobs and reconciliation

- Add Redis/worker infrastructure only if it can be run locally and configured cleanly.
- Implement a meaningful job, preferably subscription reconciliation between local state and Razorpay, with retries, bounded execution, idempotent effects, logs, and visible failure status.
- Add a local mock/test path that does not require paid infrastructure.
- Acceptance: job can be run deterministically in tests; retry does not duplicate side effects; health/readiness behavior is documented.
- Commit: `step-12: add subscription reconciliation worker`.

### Phase 14 — Security, observability, and resilience hardening

- Add request/tenant/user/operation IDs to appropriate structured logs without logging tokens, secrets, or prompts by default.
- Implement validation and size limits, secure CORS, safe error handling, rate limiting distinct from monthly quotas, secret checks, database pooling, and pagination safeguards.
- Add `/health` and `/ready` checks that distinguish app health from database/worker/provider readiness where appropriate.
- Review tenant authorization, RLS assumptions, webhook verification, and idempotency races.
- Run dependency/security checks available in the repo; report tool gaps honestly.
- Acceptance: security tests and review checklist pass; no known secrets are staged; failure responses are useful without leaking internals.
- Commit: `step-13: harden security and observability`.

### Phase 15 — End-to-end tests, CI, docs, and evidence

- Complete unit, integration, API, webhook, and E2E coverage for the acceptance list below.
- Add/finish Docker/Compose for local development and GitHub Actions for lint, type check, test, and build. Do not put secrets in CI files.
- Write `README.md`, architecture diagram, data model diagram, API examples, local setup, Supabase instructions, Ollama setup, optional Gemini instructions, Razorpay Test Mode/webhook instructions, migration/seed/test commands, security boundaries, and limitations.
- Create `EVIDENCE.md` with the exact command, expected result, actual result, and interpretation for each critical test. Do not fabricate logs or screenshots.
- Create `BUILDLOG.md` recording AI assistance, generated work, modifications, mistakes found, manual checks, and architecture decisions. Do not conceal AI assistance.
- Create `capstone.yaml` with actual run/seed/test/base URL/endpoint commands that work in this repository.
- Acceptance: a new developer can follow the README; CI commands pass in the available environment; remaining external/manual steps are explicit.
- Commit: `step-14: complete project evidence and setup guide`.

### Optional phase after all core requirements pass — Gemini adapter and stretch features

Only after Phase 15 is green, consider Gemini as an optional adapter after verifying current official documentation. Then choose stretch goals one at a time: 80%/100% usage alerts, CSV export, audit explorer, cancellation, invites, API keys, or streaming. Do not add proration/overage billing until the core system is correct and the business rules are explicit.

## 8. Acceptance criteria for the whole project

The project is not complete until these are reproducibly tested:

1. Supabase signup/login and server-side token validation work.
2. Tenant resolution works and Tenant A cannot access Tenant B usage, billing, subscription, or AI history.
3. Free and Pro plan values are database/configuration backed.
4. API and AI usage are attributed to the correct tenant and billing period.
5. Same key + same request produces one logical result and one usage event.
6. Same key + different request body returns `409`.
7. Concurrent duplicate requests cannot double-record usage.
8. Exact monthly quota boundary and concurrent-last-unit behavior are correct.
9. AI provider failure and uncertain-response behavior are documented and tested.
10. Pricing outputs exact integer minor units for deterministic vectors.
11. Simulated AI tests work without network or provider keys.
12. Ollama works if installed/configured; absence of Ollama does not break mock mode.
13. Razorpay Test Mode checkout and signature verification work when real test credentials are provided.
14. Forged webhook is rejected without state changes.
15. Duplicate webhook is processed safely once; out-of-order events do not regress subscription state incorrectly.
16. Verified Free-to-Pro transition updates effective quotas.
17. At least one background job has retry and duplicate-safety tests.
18. Dashboard metrics come from the backend and correspond to recorded usage.
19. Secrets are not committed or exposed to the frontend.
20. README, `.env.example`, `capstone.yaml`, `EVIDENCE.md`, and `BUILDLOG.md` accurately reflect the implementation.

## 9. Git and commit workflow — required after every implementation phase

Before changes, inspect `git status`. Never overwrite or revert unrelated user modifications. Never run destructive Git commands, rewrite shared history, or force-push.

After finishing each phase:

1. Run the phase's tests and relevant lint/type/build checks.
2. Inspect `git diff` and `git status`; check for secrets, generated junk, unrelated edits, and accidental files.
3. Update `BUILDLOG.md` and docs that are relevant to the completed work.
4. Stage only the intended files—do not use an unreviewed blanket add if unrelated files may exist.
5. Create the phase's commit using the commit message specified in the plan, or a similarly clear Conventional Commit.
6. If a remote and authenticated push path are configured, push the commit to the current working branch without force-pushing. If push is unavailable or rejected, keep the local commit and tell me why, with the next safe command.
7. Verify the final Git status and record the commit hash.

Never say a test, commit, or push succeeded unless you have observed the command succeed. If tests fail, fix failures in the current phase where possible. If they cannot be fixed without changing scope, explain the failure and stop; do not quietly move to the next phase or claim the phase is complete.

## 10. Required end-of-phase report

At the end of each phase, report in this exact structure:

**Phase:** number and name
**Status:** complete / blocked / incomplete
**Implemented:** brief list of real changes
**Important decisions:** decisions made and why
**Files changed:** relevant paths
**Validation:** exact commands run and pass/fail results
**Manual verification:** what was actually tested by hand; say “not performed” if not done
**Git:** commit hash/message, push status, and remaining working-tree changes
**Known issues / blockers:** specific items, or “none known”
**Next phase:** name only—do not begin it

Use concrete results, not generic assurances. Keep the report concise enough to review. Clearly distinguish automated test doubles from real integrations. If any command was not run, say so.

## 11. Starting instruction

**Begin Phase 0 now.** Inspect the repository and report the current state, assumptions, risks, and phase plan. Do not write or modify code in Phase 0. End by waiting for my `continue` message.
