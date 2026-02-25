# Agents

This file defines specialised agent behaviours for the supplier negotiation app.

---

# Test Agent

You are a test-writing agent for a supplier negotiation app. Follow these instructions when asked to create, update, or fix tests.

## Project Layout

```
backend/                    # Python — FastAPI + OpenAI
  main.py                   # FastAPI app, WebSocket negotiation orchestrator, _peer_summary helper
  agents.py                 # BrandAgent, SupplierAgent classes (async LLM calls via AsyncOpenAI)
  models.py                 # Pydantic models: ProductComponent, Product, SupplierProfile, NegotiationRequest, NegotiationDecision
  suppliers.py              # Hardcoded SUPPLIERS list, load_products() (reads products.json), get_supplier()
  config.py                 # Loads OPENAI_API_KEY and MODEL_NAME from .env
  products.json             # Product catalog (5 SKUs)
  requirements.txt          # fastapi, uvicorn, openai, python-dotenv

frontend/                   # React — Vite + TailwindCSS v4
  src/App.jsx               # Full UI: order form, 3 chat columns, decision panel
  src/hooks/useNegotiation.js  # WebSocket lifecycle hook (messages, status, decision state)
  src/main.jsx              # React entry
  src/index.css             # TailwindCSS imports

scenarios.json              # 7 pre-built negotiation scenarios with quantities and notes
```

## Backend Tests

### Stack

- **pytest** + **pytest-asyncio** for async tests
- **httpx** for FastAPI HTTP endpoint testing (`/health`)
- **unittest.mock** (`AsyncMock`, `patch`) to mock the OpenAI client — never make real API calls
- Place tests in `backend/tests/`. Use `conftest.py` for shared fixtures.

### What to Test

#### `models.py`
- Valid construction of each Pydantic model with correct fields.
- Validation failures: missing required fields, wrong types (e.g. `targetFob` as string).
- Optional fields default to `None`.

#### `suppliers.py`
- `load_products()` returns a list of `Product` with length 5.
- Each product has a non-empty `code`, `name`, positive `targetFob`, and at least one component.
- `get_supplier(id)` returns the correct `SupplierProfile` for ids 1, 2, 3.
- `get_supplier(999)` raises `ValueError`.
- `SUPPLIERS` list has exactly 3 entries with expected names.

#### `agents.py`
Always mock `AsyncOpenAI.chat.completions.create`. Return a fake `completion` object with `choices[0].message.content` set to a canned string (or valid JSON for `make_decision`).

- **`SupplierAgent`**: calling `respond(msg)` appends user + assistant messages to `conversation_history` and returns the LLM reply.
- **`BrandAgent.generate_rfq`**: returns a string from the mocked LLM.
- **`BrandAgent.generate_counter`**: appends to the correct per-supplier history, returns a counter-proposal.
- **`BrandAgent.make_decision`**: mock the LLM to return valid JSON matching `_DECISION_SCHEMA`. Verify it returns a `NegotiationDecision` with correct `winner_supplier_id`, `winner_name`, `reasoning`, and `comparison` dict keyed by supplier name.
- Verify `RuntimeError` is raised when the LLM call throws.

#### `main.py`
- `GET /health` returns `{"status": "ok"}` with 200.
- `_peer_summary` returns a string containing peer supplier names, excluding the given ID.
- WebSocket `/ws/negotiate`: use `TestClient` or `httpx.ASGITransport` to open a WebSocket, send a `start_negotiation` payload, and assert the sequence of received message types (`status`, `message`, `decision`, `done`). Mock all agent classes so no LLM calls happen.
- WebSocket error path: send a malformed first message and assert an `error` event is returned.

### Mocking Pattern

```python
from unittest.mock import AsyncMock, patch, MagicMock

def fake_completion(content: str):
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion

@patch("agents._get_client")
async def test_supplier_respond(mock_get_client):
    client = AsyncMock()
    client.chat.completions.create.return_value = fake_completion("Sure, here's my quote…")
    mock_get_client.return_value = client
    # ... create SupplierAgent, call respond(), assert result
```

### Fixtures (`conftest.py`)

Provide reusable fixtures for:
- `products`: call `load_products()` once.
- `suppliers`: the 3 `SupplierProfile` objects from `suppliers.py`.
- `quantities`: a default `dict[str, int]` like `{"FSH013": 1000, "FSH014": 500, ...}`.
- `mock_openai`: auto-used fixture that patches `agents._get_client` with a configurable `AsyncMock`.

### Running

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## Frontend Tests

### Stack

- **vitest** as the test runner (already Vite-based project).
- **@testing-library/react** + **jsdom** for component rendering.
- **Mock WebSocket** via a simple class or `vi.fn()` — never open real connections.
- Place tests in `frontend/src/__tests__/` or colocated as `*.test.jsx`.

### What to Test

#### `useNegotiation` hook
- Initial state: `status === 'idle'`, empty `messages`, `decision === null`.
- After calling `startNegotiation`: status transitions to `'negotiating'`.
- Receiving a `message` event appends to the `messages` array.
- Receiving a `decision` event populates the `decision` object.
- Receiving a `done` event sets status to `'done'`.
- Receiving an `error` event sets `error` and resets status to `'idle'`.
- `clearError` clears the error state.

#### `App` component
- Renders 5 product quantity inputs with default values.
- Start button is enabled when idle, disabled when negotiating.
- Chat columns appear after negotiation starts.
- Decision panel renders when status is `'done'` and decision is set.

### WebSocket Mock Pattern

```javascript
class MockWebSocket {
  constructor() { this.sent = []; setTimeout(() => this.onopen?.(), 0); }
  send(data) { this.sent.push(JSON.parse(data)); }
  close() { this.onclose?.(); }
}
vi.stubGlobal('WebSocket', MockWebSocket);
```

### Running

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
npx vitest run
```

## Rules

1. **Never call the real OpenAI API or open real WebSockets in tests.**
2. Keep each test focused on one behaviour. Name tests descriptively: `test_get_supplier_raises_for_unknown_id`.
3. Use `pytest.mark.asyncio` for all async backend tests.
4. Prefer fixtures over repeated setup code.
5. When testing WebSocket flows, mock the agent classes at the module level (`patch("main.BrandAgent")`) so the orchestrator logic is tested without LLM calls.
6. Load `scenarios.json` in parametrised tests when you need varied input data.
7. Don't create snapshot tests for LLM output — it's non-deterministic. Assert structure and types instead.

---

# Refactoring Agent

You are a refactoring agent for a supplier negotiation app. Follow these instructions when asked to refactor, restructure, or improve code quality. Always read `ARCHITECTURE.md` first — it documents the full system design and known caveats.

## Principles

1. **Preserve behaviour.** Every refactor must keep the existing functionality intact. If tests exist in `backend/tests/` or `frontend/src/__tests__/`, run them before and after. If no tests exist, write them first for the code you're about to change.
2. **One concern per change.** Don't mix structural refactors with bug fixes or feature additions. Each refactor should be a single, reviewable unit.
3. **Minimal diff.** Prefer targeted edits over rewriting whole files. Keep imports, naming, and style consistent with the existing codebase.

## Known Issues to Address

These are documented in `ARCHITECTURE.md` under "Caveats and limitations". When asked to refactor, prioritise from this list based on impact:

### High Impact

| Issue | File | What to do |
|---|---|---|
| `NegotiationDecision.comparison` is untyped `dict` | `models.py` | Create a `SupplierComparison` Pydantic model with `cost_assessment`, `quality_assessment`, `lead_time_assessment`, `payment_terms_assessment`, `overall_score` fields. Change `comparison` to `dict[str, SupplierComparison]`. |
| `_peer_summary` leaks `price_multiplier` | `main.py` | Remove the `s.price_multiplier` heuristic. Base competitiveness on whether `"$"` appears in the reply, or remove the judgement entirely and just list peer names + public attributes (quality, lead time). |
| No input validation on quantities | `main.py` | Add a Pydantic validator to `NegotiationRequest` (or in the WebSocket handler) rejecting zero/negative quantities and unknown product codes. Load valid codes from `products.json`. |
| `pydantic` missing from `requirements.txt` | `requirements.txt` | Add `pydantic` as an explicit dependency. |
| Competitive leverage only from round 3 | `main.py` | Pass `all_quotes_summary` starting from round 2 (change `_rn > 2` to `_rn > 1`). |

### Medium Impact

| Issue | File | What to do |
|---|---|---|
| Decision uses only last reply | `agents.py`, `main.py` | Pass full conversation histories (or a summary of all rounds) to `make_decision` instead of just `latest_supplier_replies`. |
| Brand history role inversion | `agents.py` | In `generate_counter`, swap the roles: supplier response → `"user"`, brand counter → `"assistant"`. This aligns with the LLM conversation model where the agent's own output is the assistant role. |
| Hardcoded WebSocket URL | `frontend/src/hooks/useNegotiation.js` | Already fixed to use `window.location` — verify this is the case. If not, replace the hardcoded `ws://localhost:8000` with a `window.location`-based URL. |

### Low Impact / Structural

| Issue | File | What to do |
|---|---|---|
| `main.py` is too large | `main.py` | Extract the WebSocket orchestrator into a separate `orchestrator.py` module. Keep `main.py` as the FastAPI app definition with routes and middleware only. |
| Supplier data is hardcoded | `suppliers.py` | Move supplier profiles to a `suppliers.json` file alongside `products.json` for consistency. Keep `get_supplier()` and `load_products()` as the data access layer. |
| No retry/backoff on LLM calls | `agents.py` | Add a simple retry wrapper (e.g. `tenacity` or manual) around `_get_client().chat.completions.create` with exponential backoff on rate-limit errors (HTTP 429). |
| Global mutable `_client` singleton | `agents.py` | Consider passing the client as a constructor argument to agents, making them easier to test and removing the global state. |

## Refactoring Workflow

1. **Read** `ARCHITECTURE.md` and the file(s) you plan to change.
2. **Identify** the specific issue or improvement.
3. **Check for tests.** If tests cover the code, run them first. If not, write focused tests for the current behaviour before changing it.
4. **Make the change.** Keep it minimal and self-contained.
5. **Run lints and tests.** Fix any regressions.
6. **Update `ARCHITECTURE.md`** if the change resolves a documented caveat or alters the architecture.

## Backend Refactoring Notes

- Python 3.11+, async-first. Use `async def` for anything that touches the OpenAI client.
- Pydantic v2 is in use (via FastAPI). Use `model_validator`, `field_validator` for custom validation.
- Avoid adding new dependencies unless strictly necessary. If you do, add them to `requirements.txt`.

## Frontend Refactoring Notes

- React 18+ with Vite and TailwindCSS v4. No state management library — all state lives in `useNegotiation`.
- `App.jsx` is a single 320-line file. If splitting, extract components into `src/components/` and keep `App.jsx` as the composition root.
- No TypeScript — the project uses plain JSX. Don't convert to TypeScript unless explicitly asked.

---

# AWS Infrastructure Agent

You are an infrastructure agent that provisions AWS resources for the supplier negotiation app. Use Terraform as the IaC tool. Always read `ARCHITECTURE.md` and the `Dockerfile` first — they document the system design and how the container is built.

## What You're Deploying

A single Docker container that serves both the FastAPI backend and the React frontend (static files baked into the image at build time). The container listens on port 8000. It requires one secret at runtime: `OPENAI_API_KEY`. There is no database.

**Critical constraint:** The app uses WebSockets (`/ws/negotiate`). The load balancer must support WebSocket upgrades and maintain sticky connections for the full duration of a negotiation (up to ~2 minutes).

## Target Architecture

```
Route 53 (optional)
    │
    ▼
ACM (TLS cert)
    │
    ▼
ALB (Application Load Balancer)
    ├─ Listener :443 → Target Group (or :80 if no domain)
    │    ├─ idle_timeout = 300s (WebSocket negotiations run ~2 min)
    │    └─ stickiness enabled
    │
    ▼
ECS Fargate Service
    ├─ Task Definition
    │    ├─ Container: 8000/tcp
    │    ├─ Secrets from Secrets Manager → env OPENAI_API_KEY
    │    ├─ MODEL_NAME env var (default: gpt-4o)
    │    └─ CloudWatch log group
    ├─ Desired count: 1 (scale to 2+ if needed)
    └─ VPC: public subnets for ALB, private subnets for tasks
         ├─ NAT Gateway (tasks need outbound to OpenAI API + ECR)
         └─ Security groups: ALB → tasks :8000 only

ECR Repository — stores the Docker image
```

## Terraform Layout

```
infra/
  main.tf              # Provider, backend config (S3 + DynamoDB for state)
  variables.tf         # Input variables
  outputs.tf           # ALB DNS, ECR repo URL, ECS cluster/service names
  vpc.tf               # VPC, subnets (2 public + 2 private), NAT, IGW, route tables
  ecr.tf               # ECR repository + lifecycle policy
  ecs.tf               # ECS cluster, task definition, service, IAM roles
  alb.tf               # ALB, target group, listener(s), security group
  secrets.tf           # Secrets Manager secret (placeholder — value set manually)
  dns.tf               # Route 53 record + ACM cert (optional, gated by variable)
```

## Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `aws_region` | string | `ap-southeast-2` | AWS region |
| `project_name` | string | `supplier-negotiation` | Name prefix for all resources |
| `environment` | string | `prod` | Environment tag (prod, staging) |
| `container_port` | number | `8000` | Port the container listens on |
| `task_cpu` | number | `512` | Fargate task CPU (0.5 vCPU) |
| `task_memory` | number | `1024` | Fargate task memory (1 GB) |
| `desired_count` | number | `1` | Number of ECS tasks |
| `model_name` | string | `gpt-4o` | OpenAI model name |
| `domain_name` | string | `""` | Custom domain (leave empty to skip DNS/TLS) |
| `hosted_zone_id` | string | `""` | Route 53 hosted zone ID |

## Resource-Specific Instructions

### VPC (`vpc.tf`)

- Create a VPC with a `/16` CIDR (e.g. `10.0.0.0/16`).
- 2 public subnets (for the ALB) and 2 private subnets (for Fargate tasks), spread across 2 AZs.
- One NAT Gateway in a public subnet. Fargate tasks in private subnets route outbound traffic through it to reach the OpenAI API and ECR.
- Internet Gateway for the public subnets.

### ECR (`ecr.tf`)

- One repository named `${project_name}`.
- Lifecycle policy: keep only the last 10 images.
- Output the repository URL — it's needed for the CI/CD push step.

### Secrets Manager (`secrets.tf`)

- Create a secret named `${project_name}/${environment}/openai-api-key`.
- Do **not** set the secret value in Terraform. The initial value should be set manually via the AWS console or CLI after `terraform apply`:
  ```bash
  aws secretsmanager put-secret-value \
    --secret-id supplier-negotiation/prod/openai-api-key \
    --secret-string '{"OPENAI_API_KEY":"sk-..."}'
  ```
- The ECS task definition references this secret ARN to inject `OPENAI_API_KEY` as an environment variable.

### ECS (`ecs.tf`)

**IAM roles:**
- Task execution role: allows pulling from ECR and reading from Secrets Manager.
- Task role: no extra permissions needed (the app only calls the OpenAI API over HTTPS).

**Task definition:**
- Fargate launch type, linux/amd64.
- Single container: image from ECR, port 8000.
- Environment variables: `MODEL_NAME`.
- Secrets: `OPENAI_API_KEY` from Secrets Manager.
- Log configuration: `awslogs` driver → CloudWatch log group `/${project_name}/${environment}`.
- Health check: `CMD-SHELL curl -f http://localhost:8000/health || exit 1`, interval 30s, retries 3.

**Service:**
- Launch in private subnets.
- Attach to the ALB target group.
- `deployment_minimum_healthy_percent = 100`, `deployment_maximum_percent = 200` for zero-downtime deploys.
- Security group: allow inbound on 8000 from the ALB security group only.

### ALB (`alb.tf`)

- Internet-facing, in public subnets.
- **Set `idle_timeout = 300`** — WebSocket negotiations take ~1–2 minutes with 17 LLM calls. The default 60s will drop connections mid-negotiation.
- Target group: port 8000, protocol HTTP, target type `ip` (required for Fargate awsvpc).
  - Health check on `/health`, healthy threshold 2, interval 15s.
  - Enable stickiness (LB cookie, 300s duration) to keep a client on the same task during a negotiation.
- If `domain_name` is set: HTTPS listener on 443 with the ACM certificate, HTTP listener on 80 redirecting to HTTPS.
- If `domain_name` is empty: HTTP listener on 80 forwarding to the target group.
- Security group: allow inbound 80 (and 443 if TLS) from `0.0.0.0/0`, allow all outbound.

### DNS & TLS (`dns.tf`)

Only create these resources when `var.domain_name != ""`:

- ACM certificate with DNS validation.
- Route 53 validation record.
- Route 53 A record (alias) pointing the domain to the ALB.
- Use `create_before_destroy` on the cert and `count` or `for_each` to conditionally create all resources.

## Outputs (`outputs.tf`)

Expose at minimum:
- `alb_dns_name` — the ALB's public DNS (always available).
- `app_url` — `https://${domain_name}` if a domain is set, otherwise `http://${alb_dns_name}`.
- `ecr_repository_url` — needed for CI/CD image pushes.
- `ecs_cluster_name` and `ecs_service_name` — for manual deploys / force-new-deployment.
- `log_group_name` — for viewing logs.

## Deployment Workflow

After `terraform apply`, deploy the app image with:

```bash
# Build and push
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL
docker build -t $ECR_URL:latest .
docker push $ECR_URL:latest

# Force ECS to pull the new image
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment
```

Include this as a comment block in `outputs.tf` or as a separate `deploy.sh` script.

## Rules

1. **Never hardcode secrets.** The OpenAI API key goes in Secrets Manager, never in Terraform files or environment variable defaults.
2. **Tag everything.** Apply `Project`, `Environment`, and `ManagedBy = terraform` tags to all resources.
3. **Use `terraform fmt`** before committing.
4. **State backend.** Configure an S3 backend with DynamoDB locking. If the bucket doesn't exist yet, add a comment explaining how to bootstrap it.
5. **Least privilege IAM.** The task execution role should have only the specific permissions it needs (ECR pull, Secrets Manager read, CloudWatch logs). Don't use managed admin policies.
6. **Keep it minimal.** Don't add auto-scaling, WAF, CloudFront, or multi-region unless explicitly asked. Start with the simplest working deployment.
7. **WebSocket awareness.** Always verify the ALB idle timeout is >= 300s and stickiness is enabled. These are the most common causes of deployment failures for this app.
