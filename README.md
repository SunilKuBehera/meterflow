# MeterFlow

Multi-tenant SaaS for AI/API usage metering, quota enforcement, pricing, and subscription billing.

## Architecture

- **Backend**: FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL (Supabase)
- **Frontend**: Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui
- **Auth**: Supabase Auth (JWT validation on backend)
- **Payments**: Razorpay Test Mode
- **AI**: Ollama (local) + Mock provider for testing

## Monorepo Structure

```
meterflow/
├── backend/           # FastAPI application
│   ├── api/           # Routes (/api/v1)
│   ├── core/          # Config, logging, errors, security
│   ├── db/            # SQLAlchemy session, Alembic
│   ├── models/        # ORM models
│   ├── schemas/       # Pydantic request/response
│   ├── repositories/  # Tenant-scoped data access
│   ├── services/      # Business logic
│   ├── integrations/  # AI providers, Razorpay adapter
│   ├── workers/       # Background jobs
│   └── tests/
├── frontend/          # Next.js application
│   ├── app/           # Pages (App Router)
│   ├── components/    # React components
│   └── lib/           # Supabase client, utilities
├── docker-compose.yml
└── .github/workflows/
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL (Supabase local or cloud)
- uv (recommended) or pip

### Backend Setup

```bash
cd backend

# Create virtual environment and install dependencies
uv sync --dev
# or: python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env
# Edit .env with your Supabase credentials

# Run database migrations (requires running PostgreSQL)
uv run alembic upgrade head

# Start development server
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at `http://localhost:8000`
- Health: `GET /api/v1/health`
- Ready: `GET /api/v1/ready`
- Docs: `http://localhost:8000/docs` (development only)

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment template and configure
cp .env.example .env.local
# Edit .env.local with your Supabase credentials

# Start development server
npm run dev
```

Frontend will be available at `http://localhost:3000`

### Supabase Setup

1. Create a Supabase project at https://supabase.com
2. Get credentials from Dashboard > Settings > API:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` (public)
   - `SUPABASE_SERVICE_ROLE_KEY` (secret, backend only)
   - `SUPABASE_JWT_SECRET` (for token validation)
3. Get database connection string from Dashboard > Settings > Database
4. Enable Email auth in Authentication > Providers

### Razorpay Setup (Test Mode)

1. Create account at https://razorpay.com
2. Get Test Mode keys from Dashboard > Settings > API Keys
3. Create a Plan in Dashboard > Products > Plans
4. Configure webhook URL: `https://your-domain.com/api/v1/webhooks/razorpay`

### Ollama Setup (Optional)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1

# Set in backend .env:
# AI_PROVIDER=ollama
# USAGE_MODE=real
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1
```

## Development Commands

### Backend

```bash
cd backend

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy .

# Tests
uv run pytest -v

# Tests with coverage
uv run pytest --cov=. --cov-report=term-missing

# Create migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

### Frontend

```bash
cd frontend

# Lint
npm run lint

# Type check
npm run typecheck

# Build
npm run build

# Tests
npm run test

# Tests with coverage
npm run test:coverage
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Yes | JWT secret for token validation |
| `SECRET_KEY` | Yes | Secret key for signing |
| `AI_PROVIDER` | No | `mock`, `ollama`, or `gemini` (default: mock) |
| `USAGE_MODE` | No | `simulated` or `real` (default: simulated) |
| `OLLAMA_BASE_URL` | No | Ollama API base URL |
| `OLLAMA_MODEL` | No | Ollama model name |
| `RAZORPAY_KEY_ID` | No | Razorpay Test Mode key ID |
| `RAZORPAY_KEY_SECRET` | No | Razorpay Test Mode key secret |
| `RAZORPAY_WEBHOOK_SECRET` | No | Razorpay webhook secret |
| `REDIS_URL` | No | Redis connection string |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon public key |
| `NEXT_PUBLIC_API_URL` | No | Backend API URL (default: http://localhost:8000) |

## API Endpoints (Planned)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/ready` | Readiness check |
| GET | `/api/v1/me` | Current user info |
| GET | `/api/v1/tenant` | Current tenant info |
| GET | `/api/v1/plans` | List plans |
| GET | `/api/v1/subscription` | Current subscription |
| GET | `/api/v1/usage` | Current usage |
| GET | `/api/v1/usage/history` | Usage history |
| POST | `/api/v1/ai/generate` | AI generation |
| POST | `/api/v1/billing/checkout` | Create checkout |
| POST | `/api/v1/billing/verify` | Verify payment |
| POST | `/api/v1/webhooks/razorpay` | Razorpay webhook |

## Testing

```bash
# Backend tests
cd backend && uv run pytest -v

# Frontend tests
cd frontend && npm run test

# E2E tests (when implemented)
cd frontend && npm run test:e2e
```

## CI/CD

GitHub Actions workflows in `.github/workflows/`:
- `ci.yml` - Lint, typecheck, test for both backend and frontend
- `build.yml` - Build and push Docker images (optional)

## License

Apache License 2.0 - see [LICENSE](LICENSE)