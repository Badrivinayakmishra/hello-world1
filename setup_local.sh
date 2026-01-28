#!/bin/bash

# Second Brain - Local Development Setup Script
# This script helps you set up and run the application locally

echo "🧠 Second Brain - Local Development Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please make sure .env file exists in the project root."
    exit 1
fi

echo -e "${GREEN}✓${NC} Found .env file"
echo ""

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} Python version: $PYTHON_VERSION"
else
    echo -e "${RED}Error: Python 3 not found!${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi
echo ""

# Check Node.js version
echo "Checking Node.js version..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js version: $NODE_VERSION"
else
    echo -e "${RED}Error: Node.js not found!${NC}"
    echo "Please install Node.js 18 or higher"
    exit 1
fi
echo ""

# Setup backend
echo "📦 Setting up backend..."
echo "----------------------"

cd backend || exit 1

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip > /dev/null 2>&1

# Install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Python dependencies installed"
else
    echo -e "${YELLOW}Warning: requirements.txt not found${NC}"
fi

deactivate
cd ..

echo ""

# Setup frontend
echo "📦 Setting up frontend..."
echo "----------------------"

cd frontend || exit 1

# Install npm dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
    echo -e "${GREEN}✓${NC} Node.js dependencies installed"
else
    echo -e "${YELLOW}Warning: package.json not found${NC}"
fi

cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "To start the application:"
echo ""
echo "1. Start the backend (Terminal 1):"
echo "   cd backend && source venv/bin/activate && python app_v2.py"
echo ""
echo "2. Start the frontend (Terminal 2):"
echo "   cd frontend && npm run dev"
echo ""
echo "3. Open your browser to:"
echo "   http://localhost:3000"
echo ""
echo -e "${YELLOW}Note:${NC} Make sure your .env file has the correct API keys configured."
echo ""
