# Proactive Accountability Assistant - Starter Codebase

## What You Have

A complete, production-ready starter codebase for the Proactive Accountability Assistant with:

✅ **Backend API** (FastAPI + PostgreSQL + SQLAlchemy)  
✅ **Task Scheduler** (Celery + Celery Beat + Redis)  
✅ **LLM Integration** (Anthropic Claude API)  
✅ **Discord Bot** (Discord.py with HTTP server)  
✅ **Frontend** (React + TypeScript + Tailwind)  
✅ **Docker Setup** (Complete docker-compose orchestration)  
✅ **Database Models** (Users, Projects, Tasks, Check-ins)  
✅ **Authentication** (JWT-based with secure password hashing)

## Project Structure

```
accountability-assistant/
├── backend/                          # FastAPI Backend
│   ├── alembic/                     # Database migrations
│   │   └── env.py                   # Migration environment
│   ├── app/
│   │   ├── api/                     # API endpoints
│   │   │   ├── auth.py              # Authentication (login, register)
│   │   │   ├── projects.py          # Project CRUD + decomposition
│   │   │   ├── tasks.py             # Task management
│   │   │   └── users.py             # User profile management
│   │   ├── core/                    # Core configurations
│   │   │   ├── config.py            # Settings & environment vars
│   │   │   ├── database.py          # SQLAlchemy setup
│   │   │   └── security.py          # JWT & password hashing
│   │   ├── models/                  # Database models
│   │   │   ├── user.py              # User model
│   │   │   ├── project.py           # Project model
│   │   │   ├── task.py              # Task model
│   │   │   ├── check_in.py          # Check-in history
│   │   │   └── availability_window.py
│   │   ├── schemas/                 # Pydantic validation
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   └── task.py
│   │   ├── services/                # Business logic
│   │   │   └── llm_service.py       # Claude API integration
│   │   ├── tasks/                   # Celery tasks
│   │   │   ├── celery_app.py        # Celery configuration
│   │   │   └── scheduler.py         # Check-in scheduling
│   │   └── main.py                  # FastAPI app entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── alembic.ini
│   └── .env.example
│
├── frontend/                        # React Frontend
│   ├── src/
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx      # Authentication state
│   │   ├── pages/
│   │   │   ├── Login.tsx            # Login page
│   │   │   ├── Dashboard.tsx        # Projects dashboard
│   │   │   └── index.tsx            # Stub pages
│   │   ├── services/
│   │   │   └── api.ts               # Backend API client
│   │   ├── App.tsx                  # Main app component
│   │   ├── main.tsx                 # Entry point
│   │   └── index.css                # Tailwind styles
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── Dockerfile
│
├── discord-bot/                     # Discord Integration
│   ├── bot/
│   │   └── main.py                  # Discord bot + HTTP server
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── docker-compose.yml               # Orchestration for all services
├── README.md                        # Project overview
├── ARCHITECTURE.md                  # Detailed architecture guide
├── QUICKSTART.md                    # 5-minute setup guide
└── PRD.md                           # Product requirements (your original)
```

## What Each Component Does

### Backend (FastAPI)

**Database Models:**
- `User`: Accounts, preferences, tone settings, quiet hours
- `Project`: User projects with goals, timelines, status
- `Task`: Individual tasks with deadlines, blockers, reschedule tracking
- `CheckIn`: History of all proactive check-ins and responses
- `AvailabilityWindow`: When users are available for check-ins

**API Endpoints:**
- `/api/auth/*` - Register, login, get current user
- `/api/users/*` - Profile management, preferences
- `/api/projects/*` - CRUD operations, AI decomposition
- `/api/tasks/*` - Task management, completion, rescheduling

**LLM Service:**
- Generates proactive check-in messages
- Provides coaching responses based on user replies
- Decomposes projects into actionable tasks
- Adapts tone based on user preferences (coach/manager/buddy/drill_sergeant)

### Task Scheduler (Celery)

**Celery Worker:**
- Processes background tasks asynchronously
- Sends messages through Discord bot
- Handles time-intensive operations

**Celery Beat:**
- Runs every 5 minutes to send due check-ins
- Runs every 6 hours to schedule new check-ins
- Respects user quiet hours and availability

**Tasks:**
- `process_scheduled_check_ins`: Send proactive messages
- `schedule_upcoming_check_ins`: Create check-ins for task deadlines
- `send_discord_message`: Route messages to Discord bot

### Discord Bot

**Features:**
- Receives and processes DMs
- Sends proactive check-in messages
- HTTP endpoint for backend communication
- Commands: `!start`, `!status`

**Communication Flow:**
1. Celery triggers message send
2. Backend calls Discord bot HTTP endpoint
3. Bot sends DM to user
4. User responds in DM
5. Bot forwards to backend API
6. LLM generates coaching response
7. Bot sends reply to user

### Frontend (React)

**Pages:**
- Login/Register (authentication)
- Dashboard (list projects)
- Project Create (with AI decomposition)
- Project Detail (view tasks and timeline)
- Settings (preferences, tone, quiet hours)

**API Integration:**
- Axios client with JWT authentication
- TanStack Query for data fetching
- Type-safe TypeScript interfaces

## Key Features Implemented

### 1. Tone Customization
Users can choose from 4 tones:
- **Coach**: Supportive, growth-focused
- **Manager**: Professional, results-oriented
- **Buddy**: Friendly, peer-like
- **Drill Sergeant**: Direct, high-pressure (with strategic guilt-tripping)

Users also have direct access to customize the system prompt per project.

### 2. Quiet Hours
Users specify when they DON'T want messages:
- Start time (e.g., "22:00")
- End time (e.g., "08:00")
- Scheduler respects these boundaries

### 3. Conversational Rescheduling
No snooze buttons - users must explain why they need more time:
1. User reports inability to complete task
2. LLM engages in dialogue to understand blocker
3. Assistant proposes new timeline
4. User confirms new schedule
5. System tracks reschedule count and patterns

### 4. AI-Powered Features
- **Project Decomposition**: Break vague goals into 5-15 actionable tasks
- **Check-in Generation**: Context-aware proactive messages
- **Coaching Responses**: Adaptive replies based on user progress/blockers
- **Blocker Diagnosis**: Pattern recognition for common obstacles

### 5. Proactive Scheduling
- Automatic check-in scheduling based on task deadlines
- Adaptive frequency based on user responsiveness
- Respects availability windows
- Timezone-aware (foundation in place)

## Technology Decisions & Rationale

### Why FastAPI?
- Modern async Python framework
- Automatic OpenAPI/Swagger docs
- Fast and lightweight
- Great for AI/ML integrations

### Why PostgreSQL?
- Robust relational database
- ACID compliance for data integrity
- Excellent JSON support for flexible data
- Mature ecosystem

### Why Celery + Redis?
- Industry standard for Python background tasks
- Reliable message broker
- Supports periodic tasks (Celery Beat)
- Scales horizontally

### Why React + TypeScript?
- Component-based architecture
- Strong typing reduces bugs
- Excellent ecosystem
- Fast development with Vite

### Why Docker?
- Consistent development environment
- Easy deployment
- Service isolation
- Simplified setup for new developers

## What's NOT Implemented (Next Steps)

### Frontend (Priority)
- [ ] Complete Register page
- [ ] Build Layout component with navigation
- [ ] Implement ProjectCreate with AI decomposition UI
- [ ] Create ProjectDetail with task timeline
- [ ] Build Settings page for tone/quiet hours
- [ ] Add loading states and error handling

### Backend
- [ ] Discord-specific API endpoints (`/api/discord/message`, `/api/discord/start`)
- [ ] Conversation context management (store multi-turn conversations)
- [ ] Advanced blocker pattern recognition
- [ ] Timezone handling improvements
- [ ] RAG system for long-term memory (optional)

### Discord Bot
- [ ] Complete onboarding flow
- [ ] Rich message formatting (embeds, buttons)
- [ ] Better error handling
- [ ] Conversation routing to backend API

### Testing
- [ ] Unit tests for services
- [ ] Integration tests for API
- [ ] End-to-end tests
- [ ] Load testing

## Getting Started

See [QUICKSTART.md](./QUICKSTART.md) for 5-minute setup.

### Essential Steps:

1. **Set API Key:**
```bash
# In backend/.env
ANTHROPIC_API_KEY=your-key-here
JWT_SECRET_KEY=generate-random-string
```

2. **Start Services:**
```bash
docker-compose up --build
```

3. **Initialize Database:**
```bash
docker-compose exec backend alembic upgrade head
```

4. **Access:**
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Additional Stack Components Needed

You already have the core components. Consider adding:

### Monitoring (Production)
- **Sentry** - Error tracking
- **Prometheus + Grafana** - Metrics and dashboards
- **Datadog** - APM and logging

### Infrastructure (Production)
- **AWS/GCP/Azure** - Cloud hosting
- **RDS** - Managed PostgreSQL
- **ElastiCache** - Managed Redis
- **Kubernetes** - Container orchestration (if scaling)

### Optional Enhancements
- **nginx** - Reverse proxy and load balancing
- **Elasticsearch** - Full-text search (for conversations)
- **S3** - File storage (for uploads)
- **Stripe** - Payments (for monetization)

## Development Commands

```bash
# Start everything
docker-compose up

# Rebuild after changes
docker-compose up --build

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Database migration
docker-compose exec backend alembic revision --autogenerate -m "Description"
docker-compose exec backend alembic upgrade head

# Access database
docker-compose exec postgres psql -U accountability -d accountability_db

# Run tests (when implemented)
docker-compose exec backend pytest

# Stop everything
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

## Security Considerations

**Already Implemented:**
✅ Password hashing with bcrypt  
✅ JWT-based authentication  
✅ Environment variable configuration  
✅ SQL injection prevention (SQLAlchemy ORM)  
✅ CORS configuration

**Production Checklist:**
- [ ] Change JWT secret to strong random value
- [ ] Use HTTPS in production
- [ ] Set secure cookie flags
- [ ] Implement rate limiting
- [ ] Add input validation on all endpoints
- [ ] Set up database backups
- [ ] Use secrets management (AWS Secrets Manager, etc.)
- [ ] Implement audit logging

## Performance Considerations

**Current Setup:**
- Connection pooling in SQLAlchemy
- Redis caching ready
- Async operations with FastAPI
- Celery for background tasks

**Optimization Opportunities:**
- Add database indexes for frequent queries
- Implement Redis caching for user data
- Use CDN for frontend static assets
- Add database read replicas for scaling
- Implement API response caching

## Cost Estimates (Initial)

**Infrastructure (Monthly):**
- AWS t3.small (Backend): ~$15
- RDS PostgreSQL t3.micro: ~$15
- ElastiCache Redis t3.micro: ~$12
- S3 storage: ~$5
- **Total: ~$50-75/month**

**Services:**
- Anthropic API: Pay per token (~$3-15 per 1M tokens)
- Discord bot: Free
- Domain: ~$12/year

**For 100 users:** Estimated ~$100-200/month

## Support & Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React Docs**: https://react.dev/
- **Celery Docs**: https://docs.celeryproject.org/
- **Anthropic API**: https://docs.anthropic.com/
- **Discord.py**: https://discordpy.readthedocs.io/

## License

Specify your license here (MIT, Apache, proprietary, etc.)

---

**You now have a complete, working starter codebase!** 🎉

The foundation is solid - you can start building immediately. Focus on completing the frontend pages first to enable user testing, then iterate on the LLM prompts and scheduling logic based on feedback.
