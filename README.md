# AI Structuring v3.0

**Intelligent Document Analysis & Structural Tagging Platform**

A production-ready document processing system that uses AI to automatically analyze and apply structural tags to academic documents, medical textbooks, and research papers.

---

## ✨ Features

- **AI-Powered Analysis** - Leverages Google Gemini (configurable models) for intelligent content classification
- **Batch Processing** - Process multiple documents simultaneously with queue management
- **Real-time Monitoring** - Live status updates and progress tracking
- **Cost Analytics** - Detailed token usage and cost breakdown per document
- **Professional Dashboard** - Modern, responsive UI with comprehensive analytics
- **Multiple Output Formats** - Word Styles or XML Markers

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│           React + TypeScript + Vite + TailwindCSS               │
│                    React Router + Recharts                       │
├─────────────────────────────────────────────────────────────────┤
│                         REST API                                 │
│                    Flask + SQLAlchemy                            │
├─────────────────────────────────────────────────────────────────┤
│                      Queue System                                │
│           Threading (Dev) │ Celery + Redis (Prod)               │
├─────────────────────────────────────────────────────────────────┤
│                    AI Classification                             │
│                 Google Gemini (configurable)                     │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Tech Stack

### Frontend
- React 18 with TypeScript
- Vite for development and building
- TailwindCSS for styling
- React Router for navigation
- React Query for data fetching
- Recharts for analytics visualization

### Backend
- Flask web framework
- SQLAlchemy ORM (SQLite dev fallback / PostgreSQL recommended for production)
- Celery + Redis for production queue
- Google Generative AI SDK
- python-docx for document processing

## 🚀 Quick Start

### Development Mode

```bash
# Clone and setup
cd ai-structuring-v3

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Add your GOOGLE_API_KEY
python run.py

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev

# Open http://localhost:3000
```

### Production Mode (Docker)

```bash
# Set environment variables
cp backend/.env.example backend/.env
# Edit .env with your GOOGLE_API_KEY and SECRET_KEY

# Start all services
docker-compose up -d

# Access UI at http://localhost:3000
# Backend API at http://localhost:5000
# Flower monitoring at http://localhost:5555
```

## 📱 Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Overview with stats, token usage, recent batches |
| **Process Documents** | Upload and configure document processing |
| **Batches** | List all batches with search and filtering |
| **Batch Details** | Individual batch with job-level details |
| **Analytics** | Charts for token usage and cost analysis |
| **Settings** | System configuration and status |

## 💰 Cost Tracking

The system tracks token usage and calculates costs based on the model rates configured in `backend/app/routes/api.py`.

Default model: `gemini-2.5-flash-lite`

| Type | Rate |
|------|------|
| Input Tokens | $0.10 / 1M tokens |
| Output Tokens | $0.40 / 1M tokens |

## 📊 API Endpoints

### Batches
- `POST /api/queue/batch` - Create new batch
- `GET /api/queue/batch/:id` - Get batch details
- `GET /api/queue/batches` - List all batches
- `DELETE /api/queue/batch/:id` - Delete batch
- `POST /api/queue/batch/:id/retry` - Retry failed jobs

### Jobs
- `GET /api/queue/job/:id` - Get job details
- `POST /api/queue/job/:id/cancel` - Cancel job
- `POST /api/queue/job/:id/retry` - Retry job

### Analytics
- `GET /api/queue/status` - Queue status
- `GET /api/queue/stats/tokens` - Token statistics
- `GET /api/queue/stats/daily` - Daily usage

### Downloads
- `GET /api/download/:batch_id/zip` - Download all outputs
- `GET /api/download/:batch_id/:type/:filename` - Download specific file

## 🔧 Configuration

### Environment Variables

```bash
# Required
GOOGLE_API_KEY=your_api_key

# Queue Mode
QUEUE_MODE=threading  # or 'celery' for production

# Redis
# Local dev: redis://localhost:6379/0
# Docker Compose: redis://redis:6379/0
REDIS_URL=redis://redis:6379/0

# Database
# Recommended for Docker Compose / production
DATABASE_URL=postgresql+psycopg2://ai_structuring:ai_structuring_pass@postgres:5432/ai_structuring

# Flask
SECRET_KEY=your_secret_key
FLASK_DEBUG=false
```

## 📁 Project Structure

```
ai-structuring-v3/
├── frontend/
│   ├── src/
│   │   ├── pages/          # Page components
│   │   ├── components/     # Reusable components
│   │   ├── hooks/          # React Query hooks
│   │   ├── api/            # API client
│   │   └── types/          # TypeScript types
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── routes/         # API endpoints
│   │   ├── models/         # Database models
│   │   └── services/       # Business logic
│   ├── processor/          # Document processing
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## 📄 License

Proprietary - S4Carlisle Publishing Services

---

**AI Structuring** - Document Intelligence Platform
