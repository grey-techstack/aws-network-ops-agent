# Teams Interactive Chat - Design Document

## Current State vs. Desired State

### Current Implementation (One-Shot Queries)
```
User: @AWSBot trace vision-uat.example.com
Bot:  [Shows complete trace]

User: @AWSBot what about the origin pool?
Bot:  [No context - doesn't know which domain you're asking about]
```

### Desired Implementation (Interactive Chat)
```
User: @AWSBot trace vision-uat.example.com
Bot:  [Shows complete trace]

User: @AWSBot what about the origin pool?
Bot:  [Remembers previous query - shows origin pool for vision-uat.example.com]

User: @AWSBot check the certificate expiry
Bot:  [Still remembers - shows cert expiry for vision-uat.example.com]
```

## Key Challenges

### 1. Session Management
**Problem**: Each Teams message is a separate Lambda invocation with no shared memory.

**Solution**: Use DynamoDB to store conversation history per Teams conversation ID.

```python
# DynamoDB Table: teams-chat-sessions
{
  "conversation_id": "19:xxx@thread.tacv2",  # Partition key
  "timestamp": 1707876241,                    # Sort key
  "user_name": "John Doe",
  "query": "trace vision-uat.example.com",
  "response": "...",
  "session_data": {
    "last_fqdn": "vision-uat.example.com",
    "last_lb": "lb-app-uat",
    "last_pool": "lb-app-uat-443"
  },
  "ttl": 1707962641  # Auto-delete after 24 hours
}
```

### 2. Context Awareness
**Problem**: Agent needs to understand follow-up questions without explicit context.

**Solution**: 
1. Store conversation history in DynamoDB
2. Load last N messages when processing new query
3. Pass conversation history to agent as context
4. Agent uses LangChain's conversation memory

### 3. Performance
**Problem**: Loading conversation history adds latency.

**Solution**:
1. Only load last 5-10 messages (not entire history)
2. Use DynamoDB query with limit
3. Cache session data in Lambda global variables
4. Set TTL to auto-delete old sessions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEAMS CHANNEL                                │
│  User: @AWSBot trace vision-uat.example.com                        │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                  LAMBDA HANDLER                                 │
│  1. Get conversation_id from Teams payload                      │
│  2. Load conversation history from DynamoDB                     │
│  3. Pass history + new query to Agent                          │
│  4. Agent processes with full context                          │
│  5. Save query + response to DynamoDB                          │
│  6. Send response to Teams                                     │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                  DYNAMODB TABLE                                 │
│  teams-chat-sessions                                           │
│  • conversation_id (PK)                                        │
│  • timestamp (SK)                                              │
│  • query, response, session_data                               │
│  • TTL (24 hours)                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: DynamoDB Session Storage
1. Create DynamoDB table with CloudFormation
2. Add session storage functions
3. Store each query/response pair
4. Set TTL for auto-cleanup

### Phase 2: Conversation History Loading
1. Load last N messages from DynamoDB
2. Format as conversation history
3. Pass to agent orchestrator

### Phase 3: Agent Context Enhancement
1. Update agent to accept conversation history
2. Use LangChain's ConversationBufferMemory
3. Agent can reference previous queries

### Phase 4: Smart Context Extraction
1. Extract key entities from responses (FQDNs, LB names, etc.)
2. Store in session_data for quick reference
3. Agent can use these for follow-up questions

## DynamoDB Table Schema

```yaml
TableName: teams-chat-sessions
BillingMode: PAY_PER_REQUEST
Attributes:
  - AttributeName: conversation_id
    AttributeType: S
  - AttributeName: timestamp
    AttributeType: N
KeySchema:
  - AttributeName: conversation_id
    KeyType: HASH
  - AttributeName: timestamp
    KeyType: RANGE
TimeToLiveSpecification:
  Enabled: true
  AttributeName: ttl
GlobalSecondaryIndexes: []
```

## Code Changes

### 1. New File: `src/session/session_manager.py`
```python
class TeamsSessionManager:
    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    def save_message(self, conversation_id, query, response, session_data):
        """Save query/response to DynamoDB"""
        
    def get_conversation_history(self, conversation_id, limit=10):
        """Load last N messages from DynamoDB"""
        
    def extract_session_data(self, query, response):
        """Extract key entities (FQDNs, LB names, etc.)"""
```

### 2. Update: `src/teams_webhook_handler.py`
```python
def process_query_and_send_to_teams(query, conversation_id, user_name, webhook_url):
    # NEW: Load conversation history
    session_manager = TeamsSessionManager('teams-chat-sessions')
    history = session_manager.get_conversation_history(conversation_id)
    
    # NEW: Pass history to agent
    agent_result = agent.execute_query(
        query=query,
        session_id=conversation_id,
        conversation_history=history  # NEW
    )
    
    # NEW: Save to DynamoDB
    session_data = session_manager.extract_session_data(query, output)
    session_manager.save_message(conversation_id, query, output, session_data)
```

### 3. Update: `src/agent/agent_orchestrator.py`
```python
def execute_query(self, query, session_id, conversation_history=None):
    # NEW: If conversation_history provided, add to agent memory
    if conversation_history:
        for msg in conversation_history:
            self.memory.add_message(msg['query'], msg['response'])
    
    # Execute query with full context
    result = self.agent.invoke(...)
```

## Environment Variables

Add to Lambda:
```bash
TEAMS_SESSION_TABLE_NAME=teams-chat-sessions
CONVERSATION_HISTORY_LIMIT=10
SESSION_TTL_HOURS=24
```

## IAM Permissions

Add to Lambda execution role:
```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:Query",
    "dynamodb:UpdateItem"
  ],
  "Resource": "arn:aws:dynamodb:*:*:table/teams-chat-sessions"
}
```

## Deployment Steps

1. Create DynamoDB table:
```bash
aws cloudformation deploy \
  --template-file deployment/teams-session-table.yaml \
  --stack-name teams-chat-sessions
```

2. Update Lambda code:
```bash
cd deployment
bash quick_update_teams.sh
```

3. Test interactive chat:
```bash
# In Teams:
@AWSBot trace vision-uat.example.com
@AWSBot what's the origin pool?
@AWSBot check certificate expiry
```

## Testing Strategy

### Test 1: Basic Conversation
```
User: @AWSBot trace vision-uat.example.com
Bot:  [Shows trace]

User: @AWSBot what's the origin pool?
Bot:  [Should show origin pool for vision-uat.example.com]
```

### Test 2: Context Switch
```
User: @AWSBot trace vision-uat.example.com
Bot:  [Shows trace for vision-uat]

User: @AWSBot trace demo.example.com
Bot:  [Shows trace for demo]

User: @AWSBot what's the certificate expiry?
Bot:  [Should show cert for demo.example.com, not vision-uat]
```

### Test 3: Session Expiry
```
User: @AWSBot trace vision-uat.example.com
[Wait 25 hours]
User: @AWSBot what's the origin pool?
Bot:  [Should say "I don't have context, which domain?"]
```

## Cost Estimation

### DynamoDB Costs
- Storage: ~1KB per message × 1000 messages/day = 1MB/day = $0.25/month
- Reads: 1000 queries/day × 10 messages = 10,000 reads = $1.25/month
- Writes: 1000 queries/day = 1000 writes = $1.25/month
- **Total: ~$3/month**

### Lambda Costs
- No additional cost (same invocations)
- Slightly longer execution time (+100ms for DynamoDB)

## Monitoring

### CloudWatch Metrics
- DynamoDB read/write latency
- Conversation history size
- Session cache hit rate

### CloudWatch Logs
```python
logger.info(f"Loaded {len(history)} messages from conversation {conversation_id}")
logger.info(f"Session data: {session_data}")
```

## Future Enhancements

### 1. Multi-Turn Clarification
```
User: @AWSBot trace the UAT environment
Bot:  Which domain? vision-uat.example.com or api-uat.example.com?
User: vision
Bot:  [Shows trace for vision-uat.example.com]
```

### 2. Smart Entity Recognition
```
User: @AWSBot trace vision-uat.example.com
Bot:  [Stores: last_fqdn=vision-uat.example.com, last_env=uat]

User: @AWSBot compare with production
Bot:  [Infers: compare vision-uat.example.com with vision-prd.example.com]
```

### 3. Conversation Summaries
```
User: @AWSBot summarize our conversation
Bot:  We discussed:
      1. vision-uat.example.com trace
      2. Origin pool: lb-app-uat-443
      3. Certificate expires: 2026-05-25
```

## Rollback Plan

If issues occur:
1. Disable conversation history loading (feature flag)
2. Agent works as one-shot queries (current behavior)
3. DynamoDB table remains for future use
4. No data loss

## Success Criteria

✅ User can ask follow-up questions without repeating context
✅ Agent remembers last 10 messages in conversation
✅ Session data persists across Lambda invocations
✅ Old sessions auto-delete after 24 hours
✅ Response time < 5 seconds for history loading
✅ No errors in CloudWatch logs

## Next Steps

1. Review this design with team
2. Create DynamoDB table CloudFormation template
3. Implement session manager
4. Update agent orchestrator
5. Test with sample conversations
6. Deploy to production
7. Monitor and iterate

---

**Status**: Design Phase
**Created**: 2026-02-12
**Owner**: AWS Expert Agent Team
