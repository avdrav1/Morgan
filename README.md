# Proactive Accountability Assistant

A full-stack application for AI-powered project accountability and coaching.

## Stack

- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI + Python 3.11
- **Database**: PostgreSQL
- **Cache**: Redis
- **Task Queue**: Celery + Celery Beat
- **LLM**: Anthropic Claude
- **Messaging**: Discord Bot

## Project Structure

```
accountability-assistant/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Config, security, dependencies
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── tasks/          # Celery tasks
│   │   └── main.py
│   ├── alembic/            # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # React application
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── discord-bot/            # Discord bot
│   ├── bot/
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Environment Setup

1. Copy environment files:
```bash
cp backend/.env.example backend/.env
cp discord-bot/.env.example discord-bot/.env
```

2. Update `.env` files with your credentials:
   - Anthropic API key
   - Discord bot token
   - Database credentials
   - JWT secret

### Run with Docker

```bash
docker-compose up --build
```

Services will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Discord Bot:**
```bash
cd discord-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot/main.py
```

## Database Migrations

```bash
cd backend
alembic upgrade head
```

## Running Celery Workers

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.
