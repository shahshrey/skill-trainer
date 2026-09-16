#!/bin/bash
# Install development dependencies for the project

set -e

echo "Installing development environment..."

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Linux detected"
    # Install Linux dependencies
    sudo apt-get update
    sudo apt-get install -y build-essential python3 python3-pip
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS detected"
    # Install macOS dependencies using Homebrew
    brew install python@3.11
fi

# Install Node.js dependencies
if [ -f "package.json" ]; then
    npm install
fi

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    cp .env.example .env.local
    echo "Created .env.local from template"
fi

echo "Environment setup complete!"
