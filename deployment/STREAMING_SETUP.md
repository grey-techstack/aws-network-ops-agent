# API Gateway Response Streaming Setup (Optional)

## Overview

Response streaming allows the API Gateway to stream responses from Lambda functions in real-time, providing immediate feedback to users for long-running queries. This is particularly useful for the AWS Operations Agent when queries take several seconds to complete.

**Note**: As of January 2025, API Gateway response streaming with Lambda is available but requires specific Lambda function configuration and response format.

## Prerequisites

- Lambda function configured with streaming response handler
- API Gateway REST API deployed
- Lambda function URL or API Gateway with Lambda proxy integration

## Streaming Architecture

```
User Request → API Gateway → Lambda (Streaming) → Real-time Response Chunks → User
```

### Streaming Response Format

Lambda must return responses in Server-Sent Events (SSE) format:

```
data: {"status": "processing", "message": "Querying F5 WAF..."}\n\n
data: {"status": "processing", "message": "F5 WAF data retrieved"}\n\n
data: {"status": "complete", "results": {...}}\n\n
```

## Implementation Options

### Option 1: Lambda Function URLs with Streaming (Recommended)

Lambda Function URLs support response streaming natively and are simpler to configure than API Gateway streaming.

#### 1. Update Lambda Handler for Streaming

Create a streaming response handler:

```python
# src/lambda_streaming_handler.py
import json
import time
from typing import Iterator

def generate_streaming_response(query: str, agent) -> Iterator[str]:
    """Generate streaming response chunks."""
    
    # Initial status
    yield f"data: {json.dumps({'status': 'processing', 'message': 'Starting query processing...'})}\n\n"
    time.sleep(0.1)
    
    # Query F5 WAF
    yield f"data: {json.dumps({'status': 'processing', 'message': 'Querying F5 WAF configuration...'})}\n\n"
    # ... F5 WAF query logic
    
    # Query Route53
    yield f"data: {json.dumps({'status': 'processing', 'message': 'Querying Route53 DNS records...'})}\n\n"
    # ... Route53 query logic
    
    # Query CloudFront
    yield f"data: {json.dumps({'status': 'processing', 'message': 'Querying CloudFront distributions...'})}\n\n"
    # ... CloudFront query logic
    
    # Final result
    result = agent.execute_query(query)
    yield f"data: {json.dumps({'status': 'complete', 'results': result})}\n\n"


def lambda_streaming_handler(event, context):
    """Lambda handler with streaming response."""
    
    # Parse request
    body = json.loads(event.get('body', '{}'))
    query = body.get('query')
    
    # Initialize agent
    agent = initialize_agent()
    
    # Return streaming response
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        },
        'body': generate_streaming_response(query, agent),
        'isBase64Encoded': False
    }
```

#### 2. Enable Lambda Function URL with Streaming

```bash
# Create Lambda function URL with streaming
aws lambda create-function-url-config \
  --function-name aws-ops-agent \
  --auth-type NONE \
  --invoke-mode RESPONSE_STREAM \
  --cors '{
    "AllowOrigins": ["*"],
    "AllowMethods": ["POST"],
    "AllowHeaders": ["Content-Type"],
    "MaxAge": 86400
  }'

# Get the function URL
aws lambda get-function-url-config \
  --function-name aws-ops-agent \
  --query 'FunctionUrl' \
  --output text
```

#### 3. Test Streaming Response

```bash
# Test with curl
curl -X POST https://abc123.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"query": "Trace demo.example.com"}' \
  --no-buffer

# Test with Python
import requests

response = requests.post(
    'https://abc123.lambda-url.us-east-1.on.aws/',
    json={'query': 'Trace demo.example.com'},
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

### Option 2: API Gateway with Lambda Streaming (Advanced)

API Gateway can be configured to support streaming, but it requires additional setup.

#### 1. Configure API Gateway for Streaming

The standard API Gateway REST API does not natively support Lambda response streaming. You need to use:

- **HTTP API** (API Gateway v2) with Lambda integration
- **WebSocket API** for bidirectional streaming

#### 2. HTTP API with Lambda Streaming

```bash
# Create HTTP API
aws apigatewayv2 create-api \
  --name aws-ops-agent-http-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent

# Get API endpoint
aws apigatewayv2 get-apis \
  --query 'Items[?Name==`aws-ops-agent-http-api`].ApiEndpoint' \
  --output text
```

### Option 3: WebSocket API for Real-time Updates

For true bidirectional streaming, use WebSocket API:

```bash
# Create WebSocket API
aws apigatewayv2 create-api \
  --name aws-ops-agent-websocket \
  --protocol-type WEBSOCKET \
  --route-selection-expression '$request.body.action'
```

## Client Implementation

### JavaScript/TypeScript Client

```typescript
// Streaming client for browser
async function queryAgent(query: string) {
  const response = await fetch('https://your-function-url.lambda-url.us-east-1.on.aws/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.substring(6));
        console.log('Status:', data.status, 'Message:', data.message);
        
        if (data.status === 'complete') {
          console.log('Results:', data.results);
        }
      }
    }
  }
}

// Usage
queryAgent('Trace demo.example.com');
```

### Python Client

```python
import requests
import json

def query_agent_streaming(query: str, function_url: str):
    """Query agent with streaming response."""
    
    response = requests.post(
        function_url,
        json={'query': query},
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data = json.loads(line_str[6:])
                print(f"Status: {data['status']}")
                
                if data['status'] == 'processing':
                    print(f"  Message: {data['message']}")
                elif data['status'] == 'complete':
                    print(f"  Results: {data['results']}")
                    return data['results']

# Usage
results = query_agent_streaming(
    'Trace demo.example.com',
    'https://abc123.lambda-url.us-east-1.on.aws/'
)
```

### CLI Client

```bash
#!/bin/bash
# streaming_query.sh

FUNCTION_URL="https://abc123.lambda-url.us-east-1.on.aws/"
QUERY="$1"

curl -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\"}" \
  --no-buffer | while IFS= read -r line; do
    if [[ $line == data:* ]]; then
      echo "$line" | sed 's/^data: //' | jq -r '.message // .status'
    fi
  done

# Usage
./streaming_query.sh "Trace demo.example.com"
```

## Comparison: Standard vs Streaming

| Feature | Standard Response | Streaming Response |
|---------|------------------|-------------------|
| Response Time | Wait for complete result | Immediate feedback |
| User Experience | Loading spinner | Real-time progress |
| Timeout Risk | Higher (15 min max) | Lower (continuous updates) |
| Complexity | Simple | More complex |
| Client Support | All HTTP clients | Requires streaming support |
| API Gateway | REST API | Function URL or HTTP API |

## When to Use Streaming

**Use Streaming When:**
- Queries take more than 5 seconds
- Users need real-time progress updates
- Processing involves multiple sequential steps
- User experience is critical

**Use Standard Response When:**
- Queries complete in under 3 seconds
- Simple request/response pattern is sufficient
- Client doesn't support streaming
- Simplicity is preferred

## Testing Streaming

### Test with curl

```bash
# Test streaming response
curl -X POST https://your-function-url.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"query": "Trace demo.example.com"}' \
  --no-buffer -v

# Expected output:
# data: {"status": "processing", "message": "Starting query processing..."}
# 
# data: {"status": "processing", "message": "Querying F5 WAF configuration..."}
# 
# data: {"status": "complete", "results": {...}}
```

### Test with Python

```python
import requests
import json

response = requests.post(
    'https://your-function-url.lambda-url.us-east-1.on.aws/',
    json={'query': 'Trace demo.example.com'},
    stream=True,
    timeout=300
)

print(f"Status Code: {response.status_code}")
print(f"Headers: {response.headers}")
print("\nStreaming Response:")

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

## Limitations and Considerations

1. **Lambda Timeout**: Maximum 15 minutes for Lambda execution
2. **Payload Size**: Maximum 6 MB for Lambda response payload
3. **Client Support**: Not all HTTP clients support streaming
4. **Buffering**: Some proxies may buffer responses
5. **Error Handling**: More complex error handling required
6. **Cost**: Slightly higher costs due to longer connection times

## Troubleshooting

### Common Issues

1. **Response Not Streaming**
   - Verify Lambda function URL has `RESPONSE_STREAM` invoke mode
   - Check client supports streaming (use `--no-buffer` with curl)
   - Verify Content-Type is `text/event-stream`

2. **Connection Timeout**
   - Increase client timeout settings
   - Ensure Lambda doesn't exceed 15-minute limit
   - Check for network proxies buffering responses

3. **Incomplete Responses**
   - Verify all chunks end with `\n\n`
   - Check Lambda doesn't exit before sending final chunk
   - Ensure proper error handling in streaming generator

### Debug Commands

```bash
# Test Lambda function URL configuration
aws lambda get-function-url-config \
  --function-name aws-ops-agent

# Test with verbose curl
curl -X POST https://your-function-url.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' \
  --no-buffer -v 2>&1 | grep -E "(< |> |data:)"

# Monitor Lambda logs during streaming
aws logs tail /aws/lambda/aws-ops-agent --follow
```

## Recommendation

For the AWS Operations Agent MVP, **start with standard (non-streaming) responses** using the REST API configuration from task 11.1. This provides:

- Simpler implementation
- Broader client compatibility
- Easier testing and debugging

**Add streaming support later** if:
- User feedback indicates need for real-time progress
- Queries consistently take more than 5 seconds
- Enhanced user experience is prioritized

The standard REST API can be easily upgraded to support streaming by adding a Lambda Function URL or migrating to HTTP API v2.

## Resources

- [Lambda Function URLs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html)
- [Lambda Response Streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html)
- [API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [Server-Sent Events (SSE)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
