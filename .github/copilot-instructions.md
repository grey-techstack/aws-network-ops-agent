# Copilot Instructions — AWS Operations Agent

## Build & Test

```bash
pip install -e .                      # Install in dev mode
pytest                                # All tests (with coverage)
pytest -m unit                        # Unit tests only
pytest -m property                    # Property-based tests (Hypothesis)
pytest tests/unit/test_cache_manager.py           # Single test file
pytest tests/unit/test_cache_manager.py::TestCacheManager::test_set_and_get  # Single test
```

Coverage is enabled by default via `pytest.ini` (`--cov=src --cov-report=term-missing`).

Hypothesis profiles: `default` (100 examples), `ci` (1000), `dev` (10 verbose). Set via `--hypothesis-profile=dev`.

## Architecture

This is an **AI-powered AWS infrastructure troubleshooting agent** deployed as an AWS Lambda function.

### Request Flow

```
Teams Webhook / API Gateway
  → Lambda Handler (src/lambda_handler.py or src/teams_webhook_handler.py)
    → AgentOrchestrator (src/agent/agent_orchestrator.py)
      → LangGraph ReAct Agent (create_react_agent)
        → LLM: Amazon Bedrock (Claude/Nova via src/agent/bedrock_client.py)
        → Tools: src/tools/*.py (Route53, CloudFront, ELB, F5 WAF, Athena, AWS CLI, IP Lookup)
      → CredentialManager (src/credentials/credential_manager.py) — cross-account STS AssumeRole
```

### Key Components

- **AgentOrchestrator** (`src/agent/agent_orchestrator.py`): Creates the LangGraph ReAct agent, injects `credential_manager` into tools at runtime, manages session context for follow-up queries, and extracts entities (domains, ALBs, target groups) from responses.
- **ToolExecutor** (`src/agent/tool_executor.py`): Wraps tool calls with input validation, result caching (1h TTL), and retry with exponential backoff.
- **System Prompt** (`src/agent/prompts.py`): Defines a strict FQDN tracing workflow — F5 WAF first (unless `internal.example.com`), then Route53 → CloudFront → ALB → Target Groups. This ordering is critical to the agent's behavior.

### Multi-Account & Credentials

The agent operates across multiple AWS accounts. `CredentialManager` uses STS `AssumeRole` with a configurable role name (`CROSS_ACCOUNT_ROLE_NAME`). Credentials are cached with a 5-minute expiry buffer. Route53 hosted zones live in a dedicated Core Network Account; workloads span other accounts.

### Two Lambda Entry Points

1. **`src/lambda_handler.py`** — API Gateway (REST). Accepts `{ "query": "...", "session_id": "..." }`.
2. **`src/teams_webhook_handler.py`** — Teams Outgoing Webhook. Returns immediate "Processing..." to avoid Teams' 5-second timeout, then sends results back via Incoming Webhook.

Both share the same `AgentOrchestrator` initialization pattern with Lambda container reuse (global `_agent_orchestrator`).

## Key Conventions

### Tool Pattern

All tools in `src/tools/` follow this pattern:

1. Decorated with `@tool` from `langchain_core.tools`
2. Accept `credential_manager: Annotated[Any, InjectedToolArg]` — hidden from the LLM via `InjectedToolArg`
3. Accept `request_id: Annotated[str, InjectedToolArg]` for logging correlation
4. Return `Dict[str, Any]` with results (serialized to JSON by the orchestrator wrapper)
5. Include `NEXT STEP` guidance in docstrings telling the LLM which tool to call next based on the result

The orchestrator's `_create_tools()` method wraps each tool with `inject_args()` to strip injected parameters from the schema the LLM sees.

### Environment Variables

Required Lambda environment variables (see `ENVIRONMENT_VARIABLES.md`):
- `CROSS_ACCOUNT_ROLE_NAME` — IAM role name for cross-account access (default: `aws-ops-agent-cross-account-role`)
- `F5_SECRET_NAME` — Secrets Manager secret for F5 API credentials
- `CORE_NETWORK_ACCOUNT_ID` — 12-digit AWS account ID for Route53/networking
- `WORKLOAD_ACCOUNT_IDS` — Comma-separated 12-digit account IDs
- `ATHENA_DATABASE`, `ATHENA_OUTPUT_BUCKET` — For VPC Flow Logs / CloudFront log queries
- `BEDROCK_MODEL_ID` — Override the default Bedrock model (default: `us.amazon.nova-pro-v1:0`)
- `BEDROCK_REGION` — Bedrock region (default: `us-east-1` for cross-region inference profiles)

### Testing Conventions

- Unit tests use `moto` for AWS service mocking and the `mock_aws_credentials` fixture from `conftest.py`
- Property-based tests use `hypothesis` with configurable profiles
- Test markers: `@pytest.mark.unit`, `@pytest.mark.property`, `@pytest.mark.integration`, `@pytest.mark.slow`

### Deployment

Deployment scripts live in `deployment/`. Primary entry point: `deployment/deploy_complete_infrastructure.sh`. CloudFormation templates (`.yaml`) and Terraform configs (`.tf`) are both present. See `deployment/QUICK_START.md` for the quickest path.
