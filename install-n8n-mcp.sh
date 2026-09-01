#!/bin/bash
# n8n MCP Installation Script for WSL/Linux

echo "========================================"
echo "n8n MCP Server Installation"
echo "========================================"
echo ""

# Check if Node.js is installed
echo "Step 1: Checking Node.js installation..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✓ Node.js is installed: $NODE_VERSION"
else
    echo "✗ Node.js is not installed!"
    echo "Please install Node.js:"
    echo "  sudo apt update"
    echo "  sudo apt install nodejs npm"
    exit 1
fi

# Check if npm is installed
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "✓ npm is installed: $NPM_VERSION"
else
    echo "✗ npm is not installed!"
    exit 1
fi

echo ""

# Set installation directory (Windows path accessible from WSL)
INSTALL_DIR="/mnt/c/Users/000000/n8n-mcp"
echo "Step 2: Setting up installation directory..."
echo "Installation directory: $INSTALL_DIR"

# Check if directory already exists
if [ -d "$INSTALL_DIR" ]; then
    echo "⚠ Directory already exists!"
    read -p "Do you want to remove it and reinstall? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        echo "✓ Removed existing directory"
    else
        echo "Installation cancelled."
        exit 0
    fi
fi

echo ""

# Clone the repository
echo "Step 3: Cloning n8n-mcp repository..."
if git clone https://github.com/czlonkowski/n8n-mcp.git "$INSTALL_DIR"; then
    echo "✓ Repository cloned successfully"
else
    echo "✗ Failed to clone repository!"
    echo "Alternative: Download ZIP from https://github.com/czlonkowski/n8n-mcp/archive/refs/heads/main.zip"
    exit 1
fi

echo ""

# Navigate to directory
cd "$INSTALL_DIR" || exit 1

# Install dependencies
echo "Step 4: Installing dependencies..."
echo "This may take a few minutes..."
if npm install; then
    echo "✓ Dependencies installed successfully"
else
    echo "✗ Failed to install dependencies!"
    exit 1
fi

echo ""

# Build the project
echo "Step 5: Building the project..."
if npm run build; then
    echo "✓ Build completed successfully"
else
    echo "✗ Build failed!"
    exit 1
fi

echo ""

# Rebuild (if needed)
echo "Step 6: Running rebuild..."
if npm run rebuild; then
    echo "✓ Rebuild completed successfully"
else
    echo "⚠ Rebuild failed, but this might be okay"
fi

echo ""

# Show next steps
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Next Steps:"
echo "1. Update your MCP configuration file:"
echo "   Location: C:\\Users\\000000\\.kiro\\settings\\mcp.json"
echo ""
echo "2. Add this configuration:"
echo '   "n8n-mcp": {'
echo '     "command": "node",'
echo '     "args": ["C:\\\\Users\\\\000000\\\\n8n-mcp\\\\dist\\\\mcp\\\\index.js"],'
echo '     "env": {'
echo '       "MCP_MODE": "stdio",'
echo '       "LOG_LEVEL": "error",'
echo '       "DISABLE_CONSOLE_OUTPUT": "true"'
echo '     }'
echo '   }'
echo ""
echo "3. Restart Kiro to load the new MCP server"
echo ""
echo "4. Test by asking Kiro:"
echo '   "What n8n nodes are available?"'
echo '   "Show me n8n workflow documentation"'
echo ""
echo "For more details, see: N8N_MCP_INSTALLATION_GUIDE.md"
echo ""
echo "Installation script completed!"
