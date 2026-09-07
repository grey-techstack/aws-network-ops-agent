# AWS Expert Agent - Overall Logic Documentation

## ⚠️ CRITICAL: READ BEFORE MODIFYING PROMPTS OR TOOLS

This document describes the complete AI agent logic. **ALWAYS check this before making changes.**

---

## 1. Agent Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Microsoft Teams                              │
│                   User sends message                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Power Automate Flow                           │
│  - Triggers on new channel message                              │
│  - Extracts message content and user ID                         │
│  - Sends HTTP POST to API Gateway                               │
│  - Posts Lambda response back to Teams                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (HTTP API)                        │
│  - Endpoint: your-api-id.execute-api.ap-southeast-1.amazonaws.com│
│  - Route: POST /                                                │
│  - Forwards request to Lambda                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
│              "trace app-control-dev01.example.com"                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Lambda Handler                                │
│              (teams_webhook_handler.py)                         │
│  - Receives query from API Gateway or direct invocation         │
│  - Validates API Key (x-api-key header)                         │
│  - Initializes AgentOrchestrator                                │
│  - Returns response                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Orchestrator                             │
│              (agent_orchestrator.py)                            │
│  - Creates LangChain ReAct agent                                │
│  - Registers 16 tools                                           │
│  - Uses Bedrock Claude as LLM                                   │
│  - Manages session memory                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    System Prompt                                 │
│                    (prompts.py)                                 │
│  - Defines agent capabilities                                   │
│  - Specifies tool usage rules                                   │
│  - Defines MANDATORY workflow order                             │
│  - Contains response guidelines                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LangChain ReAct Agent                         │
│  - Thinks about what to do                                      │
│  - Calls tools based on system prompt                           │
│  - Processes tool results                                       │
│  - Generates final response                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      16 Tools                                    │
│  - F5 WAF Tools (5)                                             │
│  - Route53 Tools (3)                                            │
│  - CloudFront Tools (1)                                         │
│  - ALB/NLB Tools (2)                                            │
│  - Log Analysis Tools (2)                                       │
│  - AWS CLI Tool (1)                                             │
│  - IP Lookup Tool (1)                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. MANDATORY Workflow Order (FQDN Tracing)

**⚠️ THIS IS THE MOST IMPORTANT LOGIC - DO NOT CHANGE THE ORDER**

When tracing any FQDN or domain, the agent MUST follow this order:

### ⚠️ EXCEPTION: internal.example.com Domain

**IF** the FQDN contains "internal.example.com" (e.g., myapp.internal.example.com, api.internal.example.com):
- **SKIP** F5 WAF check entirely (internal.example.com is NOT managed by F5)
- **START DIRECTLY** with Route53 DNS check (Step 2)
- This is the ONLY exception to the F5-first rule

**Reason**: F5 check takes 60+ seconds scanning 116 load balancers, causing Lambda timeouts for internal.example.com queries.

### FOR ALL OTHER DOMAINS:

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: F5 WAF CHECK (ALWAYS FIRST)                            │
│  ⚠️ EXCEPTION: Skip for internal.example.com domains                │
│  ─────────────────────────────────────────────────────────────  │
│  Tool: query_f5_load_balancer(fqdn)                             │
│  Purpose: Check if domain is managed by F5 WAF                  │
│  MANDATORY: Must actually call the tool, not just think about it│
│                                                                 │
│  If F5 found:                                                   │
│    → MUST call query_f5_origin_pool for each origin pool        │
│    → MUST display origin server details (Type, IP, Port)        │
│                                                                 │
│  If F5 not found:                                               │
│    → Continue to Step 2                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: ROUTE53 DNS CHECK                                      │
│  ─────────────────────────────────────────────────────────────  │
│  Tool: query_route53_records / list_route53_hosted_zone_records │
│  Purpose: Find DNS records for the FQDN                         │
│                                                                 │
│  HINT: If FQDN ends with .internal.example.com                     │
│    → Query the internal.example.com hosted zone directly            │
│                                                                 │
│  Actions:                                                       │
│    1. List hosted zones                                         │
│    2. Find zone containing the FQDN                             │
│    3. List DNS records in that zone                             │
│    4. Identify record type (A, CNAME, ALIAS) and target         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2.5: DNS RECORD AUTO-ROUTING (NEW)                        │
│  ─────────────────────────────────────────────────────────────  │
│  Based on the DNS record value, auto-chain to the correct tool: │
│                                                                 │
│  ┌──────────────────────────┬──────────────────────────────┐    │
│  │ DNS Record Points To     │ Next Tool                    │    │
│  ├──────────────────────────┼──────────────────────────────┤    │
│  │ *.elb.amazonaws.com      │ → ELB tools                  │    │
│  │                          │   query_load_balancer         │    │
│  │                          │   describe_load_balancer_     │    │
│  │                          │   listeners                   │    │
│  ├──────────────────────────┼──────────────────────────────┤    │
│  │ *.cloudfront.net         │ → CloudFront tools            │    │
│  │                          │   query_cloudfront_           │    │
│  │                          │   distribution                │    │
│  ├──────────────────────────┼──────────────────────────────┤    │
│  │ ves-io-*.ac.vh.ves.io   │ → F5 WAF tools                │    │
│  │                          │   query_f5_load_balancer      │    │
│  │                          │   query_f5_origin_pool        │    │
│  ├──────────────────────────┼──────────────────────────────┤    │
│  │ *.internal.example.com       │ → Route53 tools               │    │
│  │                          │   query internal.example.com zone │    │
│  ├──────────────────────────┼──────────────────────────────┤    │
│  │ Others                   │ → execute_aws_cli_command     │    │
│  └──────────────────────────┴──────────────────────────────┘    │
│                                                                 │
│  Same routing applies to F5 origin pool servers!                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: CLOUDFRONT CHECK (if applicable)                       │
│  ─────────────────────────────────────────────────────────────  │
│  Tool: query_cloudfront_distribution                            │
│  Purpose: Check if DNS points to CloudFront                     │
│                                                                 │
│  When to check:                                                 │
│    - DNS ALIAS/CNAME points to *.cloudfront.net                 │
│    - F5 origin pool points to CloudFront                        │
│                                                                 │
│  Actions:                                                       │
│    1. List distributions                                        │
│    2. Find distribution by domain alias                         │
│    3. Get distribution details (origins, behaviors)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: ALB/NLB CHECK (if applicable)                          │
│  ─────────────────────────────────────────────────────────────  │
│  Tool: query_load_balancer / describe_load_balancer_listeners   │
│  Purpose: Check if target is ALB/NLB                            │
│                                                                 │
│  When to check:                                                 │
│    - F5 origin points to *.elb.amazonaws.com                    │
│    - DNS points to *.elb.amazonaws.com                          │
│    - CloudFront origin is ALB/NLB                               │
│                                                                 │
│  Actions:                                                       │
│    1. Describe load balancers                                   │
│    2. Get listeners                                             │
│    3. Get listener rules (conditions, actions)                  │
│    4. Get target groups and health                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: SUMMARIZE COMPLETE FLOW                                │
│  ─────────────────────────────────────────────────────────────  │
│  Format:                                                        │
│    FQDN → F5 WAF → Origin Pool → CloudFront → ALB → Targets    │
│                                                                 │
│  Must include:                                                  │
│    - Each layer with details                                    │
│    - Origin server information (Type, IP, Port)                 │
│    - Health status (if applicable)                              │
│    - Certificate expiry (if applicable)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Tool Selection Strategy

### IP Address Queries

When asked about ANY public IP address, the agent MUST use `lookup_ip_address` FIRST. This tool performs three lookups in one call:
1. AWS Elastic IP / ENI check
2. SCP allowlist check (corporate-network-whitelist.tf)
3. IP geolocation (country, city, ISP, org, AS number)

Do NOT use FQDN-tracing tools (Route53, F5, CloudFront, ALB) for IP lookups unless specifically asked.

### DNS Record Auto-Routing (NEW)

After querying Route53 or F5 origin pool, inspect the record/server value and auto-chain:

| Record/Origin Points To | Pattern | Next Tool |
|---|---|---|
| ALB/NLB | `*.elb.amazonaws.com` | `query_load_balancer` / `describe_load_balancer_listeners` |
| CloudFront | `*.cloudfront.net` | `query_cloudfront_distribution` |
| F5 WAF | `ves-io-*.ac.vh.ves.io` | `query_f5_load_balancer` / `query_f5_origin_pool` |
| Internal DNS | `*.internal.example.com` | `query_route53_records` (internal.example.com zone) |
| Others | Any other value | `execute_aws_cli_command` |

### Primary Tool: AWS CLI Tool
```
execute_aws_cli_command - Use for general AWS queries not covered by specialized tools
```

**Supported Services**:
- route53 (DNS)
- elbv2 (ALB/NLB)
- cloudfront (CDN)
- ec2, rds, lambda, s3, etc.

### Specialized Tools: Use When AWS CLI Tool is Insufficient

| Tool | When to Use |
|------|-------------|
| `lookup_ip_address` | IP address queries (AWS EIP, SCP allowlist, geolocation) |
| `query_f5_load_balancer` | F5 WAF queries (NOT AWS) |
| `query_f5_origin_pool` | F5 origin pool details (NOT AWS) |
| `query_f5_load_balancer_by_name` | F5 LB by name (NOT AWS) |
| `list_f5_load_balancers` | List F5 LBs (NOT AWS) |
| `list_f5_namespaces` | List F5 namespaces (NOT AWS) |
| `query_route53_records` | FQDN-based DNS lookup |
| `query_cloudfront_distribution` | Domain-based CloudFront lookup |

---

## 4. F5 Tool Logic (CRITICAL)

### F5 API Structure

**List API** (`/http_loadbalancers`):
- Returns list of all LBs
- ❌ Does NOT include `spec` or `domains`
- ❌ Cannot search by domain

**Get API** (`/http_loadbalancers/{name}`):
- Returns full details for ONE LB
- ✅ Includes `spec` with `domains`
- ✅ Includes origin pool information

### F5 Tool Behavior

| Tool | API Used | Can Search by Domain? | Has Full Details? |
|------|----------|----------------------|-------------------|
| `query_f5_load_balancer(fqdn)` | List + Get API | ✅ Yes (queries each LB) | ✅ Yes |
| `query_f5_load_balancer_by_name(name)` | Get API | N/A | ✅ Yes |
| `query_f5_origin_pool(pool)` | Get API | N/A | ✅ Yes |

### F5 Domain Search Logic (IMPORTANT)

**Problem**: F5 List API does NOT return `spec` or `domains`
**Solution**: `query_f5_load_balancer` queries each LB individually to get domains

```python
# Step 1: Get list of all LB names from List API
items = list_api_response.get('items', [])

# Step 2: For each LB, query Get API to get full details with domains
for lb in items:
    lb_name = lb.get('name')  # Name is at top level in List API
    
    # Query Get API for this specific LB
    detail_response = get_api(f"/http_loadbalancers/{lb_name}")
    spec = detail_response.get('spec', {})
    domains = spec.get('domains', [])  # Now we have domains!
    
    # Check if FQDN matches
    if fqdn in domains:
        return lb_details
```

**Trade-off**: Slower (N+1 API calls) but CORRECT - will find all domains

---

## 5. Response Guidelines

### MANDATORY Rules

1. **F5 First Rule**: Always check F5 WAF first for any FQDN trace
   - **EXCEPTION**: Skip F5 check for internal.example.com domains (not managed by F5)
2. **Origin Pool Rule**: After F5 LB query, MUST call `query_f5_origin_pool`
3. **Origin Server Details**: MUST display Type, IP/DNS, Port
4. **No FQDN Mixing**: Each query is for ONE specific FQDN
5. **Always Use Tools**: MUST actually call tools, not just think about them
6. **No Hallucination**: Don't say "F5 check..." without calling the tool

### Response Format

```
🛡️ F5 WAF/Load Balancer
- Load Balancer: lb-app-dev-app-svc
- Domains: app-control-dev01.example.com
- Certificate Expiry: 2026-07-10 (365 days)
- Origin Pool: lb-app-dev-app-svc-443

🔗 Origin Pool (Backend Servers) - MANDATORY
- Pool: lb-app-dev-app-svc-443
- Origin Servers:
  - Type: public_ip
  - IP: 203.0.113.20
  - Port: 443
- Health Check: None
- Load Balancing: ROUND_ROBIN

📍 DNS Resolution (Route53)
- FQDN: ...
- Record Type: ...
- Target: ...

☁️ CloudFront Distribution (if applicable)
- Distribution ID: ...
- Origins: ...

⚖️ Load Balancer (ALB/NLB) (if applicable)
- Name: ...
- Listeners: ...
- Target Groups: ...

📊 Complete Flow:
FQDN → F5 WAF → Origin Pool → CloudFront → ALB → Targets
```

---

## 6. internal.example.com Exception (Performance Optimization)

### Problem
Lambda function was timing out (90 seconds) when querying domains under `internal.example.com` because:
- F5 check scans through 116 load balancers (60+ seconds)
- internal.example.com is NOT managed by F5 WAF
- This unnecessary check caused Lambda timeouts

### Solution
Added exception rule to skip F5 check for internal.example.com domains:

```
IF FQDN contains "internal.example.com":
  → SKIP F5 check
  → START with Route53 DNS check
ELSE:
  → START with F5 check (normal workflow)
```

### Performance Impact

**Before (with timeout)**:
```
Query: "check DNS for myapp.internal.example.com"
1. F5 check (scans 116 LBs) → 60+ seconds
2. Route53 DNS → 2 seconds
3. ALB check → 5 seconds
Total: 90+ seconds → TIMEOUT ❌
```

**After (no timeout)**:
```
Query: "check DNS for myapp.internal.example.com"
1. Detect "internal.example.com" → SKIP F5
2. Route53 DNS → 2 seconds
3. ALB check → 5 seconds
Total: ~10 seconds → SUCCESS ✅
```

### Implementation Locations

1. **src/agent/prompts.py** - System prompt (3 locations):
   - Top-level workflow rule
   - Mandatory workflow order section
   - Step 1: Check F5 WAF section

2. **AI_AGENT_LOGIC.md** - Documentation:
   - Section 2: MANDATORY Workflow Order
   - Section 5: Response Guidelines
   - Section 9: Quick Reference

### Testing

```bash
# Test internal.example.com (should skip F5)
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --payload '{"query": "check DNS for myapp.internal.example.com"}' \
  response.json

# Verify no F5 tool call in logs
aws logs tail /aws/lambda/aws-ops-agent-dev --since 2m | grep "query_f5_load_balancer"
# Should NOT find any F5 tool calls for internal.example.com

# Test other domain (should check F5)
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --payload '{"query": "trace vision-uat.example.com"}' \
  response.json

# Verify F5 tool call in logs
aws logs tail /aws/lambda/aws-ops-agent-dev --since 2m | grep "query_f5_load_balancer"
# Should find F5 tool calls for other domains
```

---

## 7. Anti-Hallucination Rules

The AI MUST:
- ✅ Actually invoke tools using tool_calls
- ✅ Wait for tool results before responding
- ✅ Use actual data from tool responses

The AI MUST NOT:
- ❌ Say "The F5 WAF check..." without calling the tool
- ❌ Assume results based on previous queries
- ❌ Mix data from different FQDNs
- ❌ Skip tool calls and guess the answer

---

## 8. Files Reference

| File | Purpose |
|------|---------|
| `src/agent/prompts.py` | System prompt with all rules |
| `src/agent/agent_orchestrator.py` | Agent creation and tool registration |
| `src/tools/f5_waf_tool.py` | F5 WAF tools implementation |
| `src/tools/aws_cli_tool.py` | Universal AWS CLI tool |
| `src/tools/route53_tool.py` | Route53 DNS tools |
| `src/tools/elb_tool.py` | ALB/NLB tools |
| `src/tools/cloudfront_tool.py` | CloudFront tools |
| `src/tools/ip_lookup_tool.py` | IP address lookup tool (EIP, SCP allowlist, geolocation) |
| `src/teams_webhook_handler.py` | Lambda handler with API Key validation |
| `deployment/API_GATEWAY_SETUP_V2.md` | API Gateway configuration guide |

---

## 9. Change Impact Matrix

| If You Change... | Check These... |
|------------------|----------------|
| Workflow order in prompts.py | F5-first rule preserved? |
| F5 tool logic | Null checks preserved? API structure correct? |
| Tool registration | All 16 tools registered? |
| Response guidelines | Origin server details required? |
| Anti-hallucination rules | Tool calls mandatory? |

---

## 10. Quick Reference - What NOT to Change

### ❌ DO NOT Change Workflow Order
```
F5 → Route53 → CloudFront → ALB (ALWAYS this order)
EXCEPTION: internal.example.com domains skip F5 check
```

### ❌ DO NOT Remove F5-First Rule
```
"FIRST: Check F5 WAF - ALWAYS START HERE"
"EXCEPTION: Skip for internal.example.com domains"
```

### ❌ DO NOT Remove Origin Pool Requirement
```
"MUST call query_f5_origin_pool for each origin pool"
```

### ❌ DO NOT Remove Anti-Hallucination Rules
```
"YOU MUST ACTUALLY CALL THE TOOL - Do not just think about it"
```

### ❌ DO NOT Remove Null Checks in F5 Tools
```python
if spec is None:
    spec = {}
```

---

## 11. Testing After Changes

```bash
# 1. Deploy
cd deployment
eval "$(./aws-assume-role.sh ...)"
bash quick_update_teams.sh

# 2. Test F5 query
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --cli-binary-format raw-in-base64-out \
  --cli-read-timeout 120 \
  --payload '{"query": "show me F5 load balancer for app-control-dev01.example.com"}' \
  response.json && cat response.json | jq '.body' | jq -r '.' | jq '.'

# 3. Verify tool execution
aws logs tail /aws/lambda/aws-ops-agent-dev --since 2m | grep "Tool execution"

# 4. Check for errors
aws logs tail /aws/lambda/aws-ops-agent-dev --since 2m | grep ERROR
```

---

## 12. API Gateway Integration

### Why API Gateway Instead of Function URL

Lambda Function URL 在企業環境中可能被 AWS Organizations SCP 限制，導致 403 Forbidden 錯誤。API Gateway 更穩定且相容性更好。

### Current Configuration

| Component | Value |
|-----------|-------|
| API Gateway ID | your-api-id |
| API Type | HTTP API |
| Endpoint | https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod |
| Route | POST / |
| Stage | prod (auto-deploy) |
| Lambda | aws-ops-agent-dev |

### Request Flow

```
Teams Message
    │
    ▼
Power Automate (HTTP POST)
    │
    ├── Headers: Content-Type, X-Api-Key
    ├── Body: {"query": "...", "session_id": "..."}
    │
    ▼
API Gateway (your-api-id)
    │
    ▼
Lambda (aws-ops-agent-dev)
    │
    ├── Validates X-Api-Key
    ├── Processes query with AI Agent
    │
    ▼
Response → Power Automate → Teams Reply
```

### Authentication

- API Gateway 層: 無認證 (公開)
- Lambda 層: API Key 驗證 (環境變數 API_KEY)

### Related Documentation

- 詳細設定: `deployment/API_GATEWAY_SETUP_V2.md`
- Power Automate 配置: `deployment/POWER_AUTOMATE_SETUP.md`

---

**Last Updated**: 2026-03-16
**Status**: Production
**Maintainer**: ALWAYS read this before modifying agent logic
**Recent Changes**: 
- Added IP Address Query Rule: agent uses lookup_ip_address for all IP queries (EIP, SCP allowlist, geolocation)
- Added DNS Record Auto-Routing: agent auto-chains to correct tool based on DNS record value
- Added InjectedToolArg refactor: tool descriptions maintained in single source (src/tools/*.py)
- Added API Gateway integration (replaced Function URL due to SCP restrictions)
- Added internal.example.com exception to skip F5 check (performance optimization)
