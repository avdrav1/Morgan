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

## Database Backup System

The application includes a comprehensive automated backup system for PostgreSQL.

### Quick Setup

```bash
# Set up automated daily backups
./scripts/setup-backup-cron.sh
```

### Manual Operations

```bash
# Create manual backup
./scripts/backup-database.sh

# Restore from backup
./scripts/restore-database.sh backups/daily/backup_file.sql.gz

# Test backup system
./scripts/test-backup-system.sh
```

### Features

- **Automated backups**: Daily backups via cron (2:00 AM by default)
- **Retention policy**: 7 daily, 4 weekly, 3 monthly backups
- **Compression**: Automatic gzip compression
- **Encryption**: Optional AES-256 encryption
- **Remote backup**: Support for S3, rsync, rclone
- **Easy restoration**: Simple restore from any backup

### Documentation

- [Backup System Guide](scripts/BACKUP_SYSTEM.md) - Complete documentation
- [Quick Reference](scripts/BACKUP_QUICK_REFERENCE.md) - Common commands

### Environment Variables

Add to your `.env` file:

```bash
# Required
POSTGRES_DB=accountability_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Optional
ENCRYPT_BACKUPS=true
BACKUP_ENCRYPTION_KEY=your_encryption_key
REMOTE_BACKUP=true
REMOTE_BACKUP_PATH=/path/to/remote/storage
```

For more details, see [scripts/BACKUP_SYSTEM.md](scripts/BACKUP_SYSTEM.md).
