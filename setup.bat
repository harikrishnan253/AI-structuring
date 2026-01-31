@echo off
echo ========================================
echo S4Carlisle Pre-Editor v3 Setup (Windows)
echo ========================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check for Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    pause
    exit /b 1
)

echo [1/4] Setting up Python virtual environment...
cd backend
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [2/4] Installing Python dependencies...
pip install -r requirements.txt

echo [3/4] Installing Node.js dependencies...
cd ..\frontend
call npm install

echo [4/4] Setup complete!
echo.
echo ========================================
echo To start the application:
echo.
echo 1. Set your API key:
echo    set GOOGLE_API_KEY=your_api_key_here
echo.
echo 2. Start the backend (Terminal 1):
echo    cd backend
echo    venv\Scripts\activate
echo    python run.py
echo.
echo 3. Start the frontend (Terminal 2):
echo    cd frontend
echo    npm run dev
echo.
echo 4. Open http://localhost:3000
echo ========================================
pause
