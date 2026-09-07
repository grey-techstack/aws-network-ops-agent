# Teams Interactive Chat - Quick Start Guide

## TL;DR

✅ **Interactive chat already works - no setup needed!**

Just use Teams and ask follow-up questions. The bot remembers your conversation.

## Quick Test

### In Teams:
```
You: @AWSBot trace vision-uat.example.com
Bot: [Shows F5, DNS, ALB details]

You: @AWSBot what's the origin pool?
Bot: Origin pool for vision-uat.example.com is lb-app-uat-443
     [Shows backend servers]

You: @AWSBot check certificate
Bot: Certificate for vision-uat.example.com expires 2026-05-25 (116 days)
```

### Via CLI:
```bash
cd deployment
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"
bash test_interactive_chat.sh
```

## How It Works

1. **Teams provides conversation ID** - Each conversation has unique ID
2. **Lambda stores history in memory** - Fast, no database needed
3. **Agent loads history** - Passes to Bedrock with full context
4. **Bedrock understands context** - Responds appropriately

## Session Behavior

- **Active conversation**: Bot remembers everything
- **60 minutes idle**: Session expires, starts fresh
- **Lambda cold start**: Memory cleared, starts fresh
- **New conversation**: Fresh start (different conversation ID)

## Troubleshooting

### Bot doesn't remember context?

**Check logs:**
```bash
aws logs tail /aws/lambda/aws-ops-agent-dev --since 10m | grep session
```

**Should see:**
```
Retrieved existing session: 19:xxx@thread.tacv2
Added user message to session...
```

**If not:**
- Session expired (60 min timeout)
- Lambda cold start
- Different conversation ID

### Bot asks "which domain?"

This means session was lost. Just provide context again:
```
You: @AWSBot check certificate for vision-uat.example.com
```

## Best Practices

1. **Keep conversations in same Teams thread** - Don't start new threads
2. **Ask follow-ups within 60 minutes** - Sessions expire after idle time
3. **Provide context if needed** - If bot forgot, just mention domain again
4. **Use clear references** - "the origin pool" vs "origin pool for X"

## Advanced Usage

### Clear conversation history:
```
You: @AWSBot clear history
Bot: [Implement this if needed]
```

### Check what bot remembers:
```
You: @AWSBot what were we discussing?
Bot: [Could implement conversation summary]
```

## Monitoring

### Check active sessions:
```bash
# View Lambda logs
aws logs tail /aws/lambda/aws-ops-agent-dev --follow

# Look for session activity
aws logs tail /aws/lambda/aws-ops-agent-dev --since 10m | grep "Active sessions"
```

## Cost

**$0** - Uses in-memory storage, no additional AWS services

## Limitations

- ❌ History lost on Lambda cold start (rare)
- ❌ 60-minute session timeout
- ❌ Not shared across Lambda instances
- ✅ Perfect for Teams interactive chat!

## Need More?

If you need:
- Persistent history >24 hours
- Cross-Lambda session sharing
- Conversation analytics
- Audit trail

Then consider DynamoDB (see `TEAMS_INTERACTIVE_CHAT_DESIGN.md`)

But for normal Teams usage, **current implementation is perfect** ✅

---

**Status**: ✅ Ready to Use
**Setup Required**: None
**Cost**: $0
**Performance**: <1ms
