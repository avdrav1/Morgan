# Proactive Accountability Assistant - Architecture & Setup Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Setup Instructions](#setup-instructions)
4. [Development Workflow](#development-workflow)
5. [API Documentation](#api-documentation)
6. [Next Steps](#next-steps)

---

## Architecture Overview

### System Architecture Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Discord   │◄────────┤  Discord Bot │────────►│  FastAPI    │
│   Users     │         │   (Python)   │         │   Backend   │
└─────────────┘         └──────────────┘         └─────────────┘
                               │                         │
                               │                         │
┌─────────────┐                │                         │
│   React     │────────────────┴─────────────────────────┤
│  Frontend   │                                           │
└─────────────┘                                           │
                                                          │
┌────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐    │
│  │PostgreSQL│    │  Redis   │    │Celery Worker/│    │
│  │          │    │  Cache   │    │     Beat     │    │
│  └──────────┘    └──────────┘    └──────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

**Frontend:**
- React 18 with TypeScript
- Vite (build tool)
- React Router (routing)
- TanStack Query (data fetching)
- Tailwind CSS (styling)
- Axios (HTTP client)

**Backend:**
- FastAPI (Python web framework)
- SQLAlchemy (ORM)
- Alembic (database migrations)
- Pydantic (data validation)
- JWT (authentication)
- Anthropic Claude API (LLM integration)

**Task Scheduler:**
- Celery (distributed task queue)
- Celery Beat (periodic task scheduler)
- Redis (message broker & result backend)

**Messaging:**
- Discord.py (Discord bot framework)
- aiohttp (HTTP server for bot API)

**Infrastructure:**
- PostgreSQL (relational database)
- Redis (caching & job queue)
- Docker & Docker Compose (containerization)

---

## Component Details

### 1. PostgreSQL Database

**Purpose:** Persistent storage for all application data

**Schema:**
- `users`: User accounts, preferences, quiet hours, tone settings
- `projects`: User projects with goals and timelines
- `tasks`: Individual tasks within projects
- `check_ins`: History of all proactive check-ins and conversations
- `availability_windows`: User availability schedule

**Access:**
- Port: 5432
- Default credentials: `accountability:accountability_dev`
- Database: `accountability_db`

### 2. Redis

**Purpose:** Message broker for Celery and caching layer

**Uses:**
- Celery task queue
- Celery results backend
- Session storage (future use)
- Rate limiting (future use)

**Access:**
- Port: 6379

### 3. FastAPI Backend

**Purpose:** Core API server, business logic, authentication

**Key Features:**
- RESTful API endpoints
- JWT-based authentication
- Database access via SQLAlchemy
- LLM integration for coaching and task decomposition
- Automatic API documentation (OpenAPI/Swagger)

**Endpoints:**
- `/api/auth/*` - Authentication (register, login)
- `/api/users/*` - User management
- `/api/projects/*` - Project CRUD and decomposition
- `/api/tasks/*` - Task management

**Access:**
- Port: 8000
- API Docs: http://localhost:8000/docs

### 4. Celery Worker & Beat

**Purpose:** Background task processing and scheduling

**Worker:**
- Processes asynchronous tasks
- Sends proactive check-in messages
- Handles long-running operations

**Beat (Scheduler):**
- Runs every 5 minutes to process scheduled check-ins
- Runs every 6 hours to schedule upcoming check-ins
- Checks quiet hours before sending messages

**Tasks:**
- `process_scheduled_check_ins`: Send due check-ins
- `schedule_upcoming_check_ins`: Create check-ins for upcoming task deadlines
- `send_discord_message`: Send message via Discord bot

### 5. Discord Bot

**Purpose:** Interface for proactive messaging and user interactions

**Features:**
- Receives and responds to DMs
- Sends proactive check-ins
- Processes user responses
- HTTP endpoint for backend to trigger messages

**Commands:**
- `!start` - Begin onboarding
- `!status` - Check current projects/tasks
- DM conversations for coaching

**Access:**
- Internal HTTP server: Port 8001
- Connects to Discord API

### 6. React Frontend

**Purpose:** Web interface for project setup and management

**Key Pages:**
- **Login/Register**: Authentication
- **Dashboard**: List of projects
- **Project Create**: AI-assisted project decomposition
- **Project Detail**: View tasks, timelines, check-ins
- **Settings**: User preferences, tone, quiet hours

**Access:**
- Port: 5173
- Dev server with hot reload

---

## Setup Instructions

### Prerequisites

1. **Docker & Docker Compose**
   - [Install Docker Desktop](https://www.docker.com/products/docker-desktop)

2. **Anthropic API Key**
   - [Get API key from Anthropic Console](https://console.anthropic.com/)

3. **Discord Bot Token** (for Discord integration)
   - [Create bot in Discord Developer Portal](https://discord.com/developers/applications)
   - Enable "Message Content Intent" in bot settings

### Initial Setup

**1. Clone and navigate to project:**
```bash
cd accountability-assistant
```

**2. Configure environment variables:**

Backend (required):
```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set:
- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `JWT_SECRET_KEY` - Generate with: `openssl rand -hex 32`

Discord Bot (optional for Phase 1):
```bash
cp discord-bot/.env.example discord-bot/.env
```

Edit `discord-bot/.env` and set:
- `DISCORD_TOKEN` - Your Discord bot token

**3. Start all services with Docker Compose:**
```bash
docker-compose up --build
```

This will start:
- PostgreSQL (localhost:5432)
- Redis (localhost:6379)
- FastAPI backend (localhost:8000)
- Celery worker
- Celery beat
- Discord bot
- React frontend (localhost:5173)

**4. Initialize the database:**

First time only:
```bash
docker-compose exec backend alembic upgrade head
```

**5. Access the application:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Development Workflow

### Running Individual Services Locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Celery Worker:**
```bash
cd backend
source venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info
```

**Celery Beat:**
```bash
cd backend
source venv/bin/activate
celery -A app.tasks.celery_app beat --loglevel=info
```

**Discord Bot:**
```bash
cd discord-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot/main.py
```

### Database Migrations

**Create a new migration:**
```bash
docker-compose exec backend alembic revision --autogenerate -m "Description of changes"
```

**Apply migrations:**
```bash
docker-compose exec backend alembic upgrade head
```

**Rollback migration:**
```bash
docker-compose exec backend alembic downgrade -1
```

### Viewing Logs

**All services:**
```bash
docker-compose logs -f
```

**Specific service:**
```bash
docker-compose logs -f backend
docker-compose logs -f celery-worker
docker-compose logs -f discord-bot
```

---

## API Documentation

### Authentication Flow

**1. Register:**
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "John Doe"
}
```

**2. Login:**
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secure_password
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**3. Authenticated requests:**
```http
GET /api/users/me
Authorization: Bearer eyJ...
```

### Core Workflows

**Project Creation & Decomposition:**
```http
# 1. Create project
POST /api/projects/
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "title": "Launch Newsletter",
  "description": "Create and launch indie game dev newsletter",
  "goal": "Build audience and document journey",
  "project_tone": "coach"
}

# 2. AI-powered task decomposition
POST /api/projects/{project_id}/decompose
Authorization: Bearer eyJ...
```

**Task Management:**
```http
# Complete a task
POST /api/tasks/{task_id}/complete
Authorization: Bearer eyJ...

# Reschedule a task
POST /api/tasks/{task_id}/reschedule
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "new_due_date": "2025-12-01T10:00:00Z",
  "reason": "Need more time for research"
}
```

---

## Next Steps

### Immediate Development Tasks

1. **Complete Frontend Pages:**
   - Implement Register page
   - Build Layout component with navigation
   - Create ProjectCreate form with AI decomposition
   - Build ProjectDetail view with task timeline
   - Implement Settings page for preferences

2. **Backend Enhancements:**
   - Add Discord-specific API endpoints (`/api/discord/*`)
   - Implement conversation context management
   - Add RAG system for long-term memory (if needed)
   - Build quiet hours validation logic
   - Add timezone handling

3. **Discord Bot Integration:**
   - Complete onboarding flow
   - Implement conversation routing to LLM
   - Add rich message formatting
   - Handle error cases gracefully

4. **Testing:**
   - Write unit tests for core services
   - Add integration tests for API endpoints
   - Test Celery task scheduling
   - End-to-end testing with Discord bot

### Phase 1 Goals

- [x] Core infrastructure
- [ ] Complete onboarding flow
- [ ] Basic project decomposition
- [ ] Proactive check-ins working
- [ ] Discord bot responding to DMs
- [ ] 10 beta users testing

### Future Enhancements

**Phase 2:**
- Multi-project support
- Advanced scheduling algorithm
- Pattern recognition for blockers
- Weekly digest generation
- Web push notifications

**Phase 3:**
- Native mobile apps
- SMS support
- Collaborative projects
- Advanced analytics
- RAG-based context memory

**Phase 4:**
- Slack integration
- API for third-party integrations
- Team/enterprise features
- Advanced reporting

---

## Troubleshooting

### Common Issues

**Database connection errors:**
```bash
# Restart PostgreSQL
docker-compose restart postgres

# Check connection
docker-compose exec postgres psql -U accountability -d accountability_db
```

**Celery not processing tasks:**
```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# Restart Celery services
docker-compose restart celery-worker celery-beat
```

**Frontend can't connect to backend:**
- Check `VITE_API_URL` in frontend `.env`
- Verify backend is running on port 8000
- Check CORS settings in `backend/app/core/config.py`

**Discord bot not responding:**
- Verify bot token in `.env`
- Check bot has necessary Discord permissions
- Ensure "Message Content Intent" is enabled
- Check logs: `docker-compose logs discord-bot`

### Getting Help

- Check API documentation: http://localhost:8000/docs
- View logs for errors
- Verify environment variables are set correctly
- Ensure all services are running: `docker-compose ps`

---

## Contributing

When adding new features:

1. Create database models in `backend/app/models/`
2. Add Pydantic schemas in `backend/app/schemas/`
3. Implement business logic in `backend/app/services/`
4. Create API endpoints in `backend/app/api/`
5. Generate and apply migrations
6. Update frontend API service
7. Build UI components
8. Write tests

Remember to follow the existing code structure and patterns!
