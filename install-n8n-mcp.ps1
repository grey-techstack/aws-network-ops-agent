# n8n MCP Installation Script for Windows
# Run this in PowerShell

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "n8n MCP Server Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Node.js is installed
Write-Host "Step 1: Checking Node.js installation..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "✓ Node.js is installed: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Node.js is not installed!" -ForegroundColor Red
    Write-Host "Please install Node.js from: https://nodejs.org/" -ForegroundColor Yellow
    Write-Host "Recommended: LTS version (v20.x or later)" -ForegroundColor Yellow
    exit 1
}

# Check if npm is installed
try {
    $npmVersion = npm --version
    Write-Host "✓ npm is installed: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ npm is not installed!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Set installation directory
$installDir = "C:\Users\000000\n8n-mcp"
Write-Host "Step 2: Setting up installation directory..." -ForegroundColor Yellow
Write-Host "Installation directory: $installDir" -ForegroundColor Cyan

# Check if directory already exists
if (Test-Path $installDir) {
    Write-Host "⚠ Directory already exists!" -ForegroundColor Yellow
    $response = Read-Host "Do you want to remove it and reinstall? (y/n)"
    if ($response -eq "y") {
        Remove-Item -Path $installDir -Recurse -Force
        Write-Host "✓ Removed existing directory" -ForegroundColor Green
    } else {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""

# Clone the repository
Write-Host "Step 3: Cloning n8n-mcp repository..." -ForegroundColor Yellow
try {
    git clone https://github.com/czlonkowski/n8n-mcp.git $installDir
    Write-Host "✓ Repository cloned successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to clone repository!" -ForegroundColor Red
    Write-Host "Alternative: Download ZIP from https://github.com/czlonkowski/n8n-mcp/archive/refs/heads/main.zip" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Navigate to directory
Set-Location $installDir

# Install dependencies
Write-Host "Step 4: Installing dependencies..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Cyan
try {
    npm install
    Write-Host "✓ Dependencies installed successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to install dependencies!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Build the project
Write-Host "Step 5: Building the project..." -ForegroundColor Yellow
try {
    npm run build
    Write-Host "✓ Build completed successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Rebuild (if needed)
Write-Host "Step 6: Running rebuild..." -ForegroundColor Yellow
try {
    npm run rebuild
    Write-Host "✓ Rebuild completed successfully" -ForegroundColor Green
} catch {
    Write-Host "⚠ Rebuild failed, but this might be okay" -ForegroundColor Yellow
}

Write-Host ""

# Test the installation
Write-Host "Step 7: Testing the installation..." -ForegroundColor Yellow
Write-Host "Starting MCP server (press Ctrl+C to stop)..." -ForegroundColor Cyan
Write-Host ""

# Show next steps
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Update your MCP configuration file:" -ForegroundColor White
Write-Host "   Location: C:\Users\000000\.kiro\settings\mcp.json" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Add this configuration:" -ForegroundColor White
Write-Host '   "n8n-mcp": {' -ForegroundColor Cyan
Write-Host '     "command": "node",' -ForegroundColor Cyan
Write-Host '     "args": ["C:\\Users\\000000\\n8n-mcp\\dist\\mcp\\index.js"],' -ForegroundColor Cyan
Write-Host '     "env": {' -ForegroundColor Cyan
Write-Host '       "MCP_MODE": "stdio",' -ForegroundColor Cyan
Write-Host '       "LOG_LEVEL": "error",' -ForegroundColor Cyan
Write-Host '       "DISABLE_CONSOLE_OUTPUT": "true"' -ForegroundColor Cyan
Write-Host '     }' -ForegroundColor Cyan
Write-Host '   }' -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Restart Kiro to load the new MCP server" -ForegroundColor White
Write-Host ""
Write-Host "4. Test by asking Kiro:" -ForegroundColor White
Write-Host '   "What n8n nodes are available?"' -ForegroundColor Cyan
Write-Host '   "Show me n8n workflow documentation"' -ForegroundColor Cyan
Write-Host ""
Write-Host "For more details, see: N8N_MCP_INSTALLATION_GUIDE.md" -ForegroundColor Yellow
Write-Host ""

# Optional: Open the config file
$response = Read-Host "Do you want to open the MCP config file now? (y/n)"
if ($response -eq "y") {
    notepad "C:\Users\000000\.kiro\settings\mcp.json"
}

Write-Host ""
Write-Host "Installation script completed!" -ForegroundColor Green
