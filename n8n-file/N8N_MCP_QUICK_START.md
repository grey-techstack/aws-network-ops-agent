# n8n MCP Quick Start Guide

## 📋 What You Need

1. **Node.js** installed (v20.x or later)
2. **Git** (optional, for cloning)
3. **Kiro** with MCP support

## 🚀 Quick Installation (3 Methods)

### Method 1: PowerShell Script (Recommended for Windows)

```powershell
# Open PowerShell in the project directory
cd C:\Users\000000\Downloads\Azure\AI-q\aws-expert-agent

# Run the installation script
.\install-n8n-mcp.ps1
```

### Method 2: Bash Script (For WSL)

```bash
# Open WSL terminal
cd /mnt/c/Users/000000/Downloads/Azure/AI-q/aws-expert-agent

# Make script executable
chmod +x install-n8n-mcp.sh

# Run the installation script
./install-n8n-mcp.sh
```

### Method 3: Manual Installation

```bash
# 1. Clone the repository
cd C:\Users\000000
git clone https://github.com/czlonkowski/n8n-mcp.git
cd n8n-mcp

# 2. Install dependencies
npm install

# 3. Build the project
npm run build
npm run rebuild

# 4. Test
npm start
```

## ⚙️ Configuration

After installation, update your MCP config:

**File**: `C:\Users\000000\.kiro\settings\mcp.json`

**Add this section** to the `mcpServers` object:

```json
"n8n-mcp": {
  "command": "node",
  "args": ["C:\\Users\\000000\\n8n-mcp\\dist\\mcp\\index.js"],
  "env": {
    "MCP_MODE": "stdio",
    "LOG_LEVEL": "error",
    "DISABLE_CONSOLE_OUTPUT": "true"
  },
  "disabled": false,
  "autoApprove": []
}
```

**Complete example** is available in: `mcp-config-with-n8n.json`

## 🔌 Connect to Your n8n Instance (Optional)

If you have an n8n instance running, add these environment variables:

```json
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
```

## ✅ Verification

1. **Restart Kiro** after updating the config
2. **Check MCP panel** in Kiro to see if n8n-mcp is connected
3. **Test with queries**:
   - "What n8n nodes are available?"
   - "Show me n8n HTTP Request node documentation"
   - "List my n8n workflows" (if API connected)

## 🎯 What You Can Do

### Without n8n API (Documentation Only)
- ✅ Get n8n node documentation
- ✅ Search n8n documentation
- ✅ Learn about n8n workflows
- ✅ Get help with n8n concepts

### With n8n API (Full Features)
- ✅ List all workflows
- ✅ Get workflow details
- ✅ Execute workflows
- ✅ Create new workflows
- ✅ Update workflows
- ✅ Delete workflows
- ✅ List executions
- ✅ Get execution details
- ✅ Retry failed executions

## 📚 Example Queries

```
"Show me how to use the HTTP Request node in n8n"
"What parameters does the Slack node accept?"
"List all my n8n workflows"
"Execute the workflow named 'Daily Report'"
"What's the status of the last execution?"
"Create a workflow that sends email notifications"
"How do I use webhooks in n8n?"
```

## 🔧 Troubleshooting

### Node.js Not Found
```bash
# Install Node.js
# Download from: https://nodejs.org/
# Or use package manager:
winget install OpenJS.NodeJS.LTS
```

### Git Clone Fails
```bash
# Download ZIP instead
# URL: https://github.com/czlonkowski/n8n-mcp/archive/refs/heads/main.zip
# Extract to: C:\Users\000000\n8n-mcp
```

### Build Errors
```bash
# Clear cache and rebuild
cd C:\Users\000000\n8n-mcp
rm -rf node_modules
npm install
npm run build
```

### MCP Server Not Responding
1. Check the path in mcp.json is correct
2. Test manually: `node C:\Users\000000\n8n-mcp\dist\mcp\index.js`
3. Check Kiro's MCP logs
4. Restart Kiro

## 📁 Files Created

- `N8N_MCP_INSTALLATION_GUIDE.md` - Detailed installation guide
- `N8N_MCP_QUICK_START.md` - This file (quick reference)
- `install-n8n-mcp.ps1` - PowerShell installation script
- `install-n8n-mcp.sh` - Bash installation script
- `mcp-config-with-n8n.json` - Example MCP configuration

## 🔗 Resources

- **n8n MCP GitHub**: https://github.com/czlonkowski/n8n-mcp
- **n8n Documentation**: https://docs.n8n.io/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Node.js Download**: https://nodejs.org/

## 💡 Tips

1. **Start with documentation mode** (no API) to learn n8n
2. **Connect API later** when you have an n8n instance
3. **Use auto-approve** for trusted tools to avoid confirmation prompts
4. **Check logs** in Kiro's MCP panel if something doesn't work
5. **Update regularly**: `cd C:\Users\000000\n8n-mcp && git pull && npm install && npm run build`

---

**Need Help?** Check the detailed guide: `N8N_MCP_INSTALLATION_GUIDE.md`
