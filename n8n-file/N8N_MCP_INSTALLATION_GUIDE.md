# n8n MCP Server Installation Guide

## Prerequisites

1. **Install Node.js** (if not already installed)
   - Download from: https://nodejs.org/
   - Recommended version: LTS (v20.x or later)
   - Verify installation:
     ```bash
     node --version
     npm --version
     ```

## Installation Steps

### Step 1: Clone the n8n-mcp Repository

Open PowerShell or Command Prompt and run:

```bash
# Navigate to a suitable directory (e.g., your home directory)
cd C:\Users\000000

# Clone the repository
git clone https://github.com/czlonkowski/n8n-mcp.git

# Navigate into the directory
cd n8n-mcp
```

**Alternative if git clone fails:**
- Download ZIP from: https://github.com/czlonkowski/n8n-mcp/archive/refs/heads/main.zip
- Extract to: `C:\Users\000000\n8n-mcp`

### Step 2: Install Dependencies

```bash
npm install
```

### Step 3: Build the Project

```bash
npm run build
npm run rebuild
```

### Step 4: Test the Installation

```bash
npm start
```

If successful, you should see the MCP server starting without errors.

## Configuration

### Option A: Documentation Tools Only (Recommended for Start)

Edit your MCP configuration file:
- Location: `C:\Users\000000\.kiro\settings\mcp.json`

Add the n8n-mcp server configuration:

```json
{
  "mcpServers": {
    "aws-knowledge-mcp": {
      "type": "http",
      "url": "https://knowledge-mcp.global.api.aws"
    },
    "AWS MCP Server": {
      "type": "stdio",
      "command": "C:\\Users\\000000\\OneDrive\\File\\projects\\aws-tools\\aws-network-ops-agent\\.venv\\Scripts\\uvx.exe",
      "args": ["mcp-proxy-for-aws@latest", "https://aws-mcp.us-east-1.api.aws/mcp"]
    },
    "n8n-mcp": {
      "command": "node",
      "args": ["C:\\Users\\000000\\n8n-mcp\\dist\\mcp\\index.js"],
      "env": {
        "MCP_MODE": "stdio",
        "LOG_LEVEL": "error",
        "DISABLE_CONSOLE_OUTPUT": "true"
      }
    }
  },
  "inputs": []
}
```

### Option B: Full n8n Integration (with API Access)

If you want to connect to an actual n8n instance:

```json
{
  "mcpServers": {
    "aws-knowledge-mcp": {
      "type": "http",
      "url": "https://knowledge-mcp.global.api.aws"
    },
    "AWS MCP Server": {
      "type": "stdio",
      "command": "C:\\Users\\000000\\OneDrive\\File\\projects\\aws-tools\\aws-network-ops-agent\\.venv\\Scripts\\uvx.exe",
      "args": ["mcp-proxy-for-aws@latest", "https://aws-mcp.us-east-1.api.aws/mcp"]
    },
    "n8n-mcp": {
      "command": "node",
      "args": ["C:\\Users\\000000\\n8n-mcp\\dist\\mcp\\index.js"],
      "env": {
        "MCP_MODE": "stdio",
        "LOG_LEVEL": "error",
        "DISABLE_CONSOLE_OUTPUT": "true",
        "N8N_API_URL": "https://your-n8n-instance.com",
        "N8N_API_KEY": "your-api-key-here"
      }
    }
  },
  "inputs": []
}
```

## n8n MCP Capabilities

Once installed, the n8n MCP server provides:

### Documentation Tools
- **get_workflow_documentation**: Get documentation for n8n workflows
- **get_node_documentation**: Get documentation for specific n8n nodes
- **search_documentation**: Search n8n documentation

### Workflow Management Tools (requires n8n API connection)
- **list_workflows**: List all workflows in your n8n instance
- **get_workflow**: Get details of a specific workflow
- **execute_workflow**: Execute a workflow
- **create_workflow**: Create a new workflow
- **update_workflow**: Update an existing workflow
- **delete_workflow**: Delete a workflow

### Execution Management Tools (requires n8n API connection)
- **list_executions**: List workflow executions
- **get_execution**: Get details of a specific execution
- **retry_execution**: Retry a failed execution

## Verification

After updating the MCP configuration:

1. **Restart Kiro** to reload the MCP configuration
2. **Test the connection** by asking Kiro:
   - "What n8n nodes are available?"
   - "Show me n8n workflow documentation"
   - "List my n8n workflows" (if API is configured)

## Troubleshooting

### Issue: "Cannot find module"
**Solution**: Make sure you ran `npm install` and `npm run build`

### Issue: "node: command not found"
**Solution**: 
- Install Node.js from https://nodejs.org/
- Make sure Node.js is in your PATH
- Restart your terminal/PowerShell

### Issue: "Permission denied"
**Solution**: Run PowerShell as Administrator

### Issue: MCP server not responding
**Solution**:
1. Check the path in mcp.json is correct
2. Test manually: `node C:\Users\000000\n8n-mcp\dist\mcp\index.js`
3. Check logs in Kiro's MCP panel

### Issue: Git clone fails with 403
**Solution**:
1. Download ZIP manually from GitHub
2. Or try with SSH: `git clone git@github.com:czlonkowski/n8n-mcp.git`
3. Or configure git proxy if behind corporate firewall

## Next Steps

Once n8n MCP is installed and configured:

1. **Explore n8n documentation** through Kiro
2. **Connect to your n8n instance** (if you have one)
3. **Manage workflows** directly from Kiro
4. **Integrate n8n workflows** with your AWS operations

## Useful Commands

```bash
# Update n8n-mcp to latest version
cd C:\Users\000000\n8n-mcp
git pull
npm install
npm run build

# Test the MCP server manually
npm start

# Check for errors
node C:\Users\000000\n8n-mcp\dist\mcp\index.js
```

## Resources

- n8n MCP GitHub: https://github.com/czlonkowski/n8n-mcp
- n8n Documentation: https://docs.n8n.io/
- MCP Protocol: https://modelcontextprotocol.io/
- Kiro MCP Guide: Check Kiro's documentation for MCP configuration

## Example Usage with Kiro

Once configured, you can ask Kiro:

```
"Show me how to use the HTTP Request node in n8n"
"List all my n8n workflows"
"Execute the workflow named 'Daily Report'"
"What's the status of the last execution?"
"Create a new workflow that sends Slack notifications"
```

---

**Note**: This guide assumes you're using Windows. Adjust paths accordingly if using Linux/Mac.
