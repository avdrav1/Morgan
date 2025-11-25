# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered project accountability assistant with proactive check-ins via Discord. Users create projects, the LLM decomposes them into tasks, and Celery schedules proactive coaching messages.

## Architecture

- **Frontend**: React 18 + TypeScript + Vite (port 5173)
- **Backend**: FastAPI + SQLAlchemy + Pydantic (port 8000)
- **Database**: PostgreSQL with Alembic migrations
- **Task Queue**: Celery + Celery Beat with Redis broker
- **Discord Bot**: discord.py with internal HTTP server (port 8001)
- **LLM**: Anthropic Claude API via `backend/app/services/llm_service.py`

## Commands

### Docker (recommended)
```bash
docker-compose up --build                    # Start all services
docker-compose exec backend alembic upgrade head  # Run migrations
docker-compose logs -f backend               # View service logs
```

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install && npm run dev
```

**Celery:**
```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

**Discord Bot:**
```bash
cd discord-bot
python bot/main.py
```

### Database Migrations
```bash
alembic revision --autogenerate -m "Description"  # Create migration
alembic upgrade head                              # Apply migrations
alembic downgrade -1                              # Rollback one
```

## Code Structure

Backend follows this pattern for new features:
1. Models in `backend/app/models/`
2. Pydantic schemas in `backend/app/schemas/`
3. Business logic in `backend/app/services/`
4. API endpoints in `backend/app/api/`

Key files:
- `backend/app/core/config.py` - Settings and env vars
- `backend/app/core/database.py` - DB session management
- `backend/app/tasks/scheduler.py` - Celery task definitions
- `backend/app/services/llm_service.py` - Claude API integration

## Environment Variables

Required in `backend/.env`:
- `ANTHROPIC_API_KEY` - Claude API key
- `JWT_SECRET_KEY` - Generate with `openssl rand -hex 32`

Required in `discord-bot/.env`:
- `DISCORD_TOKEN` - Discord bot token

## API Documentation

Available at http://localhost:8000/docs when backend is running.
