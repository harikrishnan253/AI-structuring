#!/bin/bash

echo "========================================"
echo "S4Carlisle Pre-Editor v3 Setup"
echo "========================================"
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed"
    exit 1
fi

echo "[1/4] Setting up Python virtual environment..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "[2/4] Installing Python dependencies..."
pip install -r requirements.txt

echo "[3/4] Installing Node.js dependencies..."
cd ../frontend
npm install

echo "[4/4] Setup complete!"
echo
echo "========================================"
echo "To start the application:"
echo
echo "1. Set your API key:"
echo "   export GOOGLE_API_KEY=your_api_key_here"
echo
echo "2. Start the backend (Terminal 1):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python run.py"
echo
echo "3. Start the frontend (Terminal 2):"
echo "   cd frontend"
echo "   npm run dev"
echo
echo "4. Open http://localhost:3000"
echo "========================================"
