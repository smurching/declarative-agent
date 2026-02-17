#!/bin/bash
set -e

echo "================================"
echo "Agent Backend Setup"
echo "================================"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✓ uv is installed"

# Check if databricks CLI is installed
if ! command -v databricks &> /dev/null; then
    echo "❌ databricks CLI is not installed. Please install it first:"
    echo "   pip install databricks-cli"
    exit 1
fi

echo "✓ databricks CLI is installed"

# Install dependencies
echo ""
echo "Installing dependencies..."
uv sync

echo "✓ Dependencies installed"

# Check if .env exists
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found. Copying .env.example to .env"
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "📝 Please edit .env with your Databricks configuration:"
    echo "   - DATABRICKS_HOST"
    echo "   - DATABRICKS_TOKEN"
    echo "   - PGHOST, PGUSER, PGDATABASE"
    echo "   - WORKSPACE_ID"
    echo ""
else
    echo "✓ .env file exists"
fi

echo ""
echo "================================"
echo "Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your configuration (if not already done)"
echo "  2. Run migrations: python scripts/migrate.py"
echo "  3. Start the server: uvicorn server.main:app --reload"
echo "  4. Test the API: python scripts/test_api.py"
echo ""
echo "To deploy to Databricks Apps:"
echo "  databricks bundle validate"
echo "  databricks bundle deploy"
echo "  databricks bundle run agent_backend"
echo ""
