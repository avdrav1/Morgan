# Quick Start Guide

Get the Proactive Accountability Assistant running in 5 minutes.

## Prerequisites

- Docker Desktop installed
- Anthropic API key ([get one here](https://console.anthropic.com/))
- (Optional) Discord bot token for messaging

## Setup

### 1. Configure Environment

```bash
# Backend configuration
cp backend/.env.example backend/.env
```

Edit `backend/.env` and add:
```env
ANTHROPIC_API_KEY=your-actual-api-key-here
JWT_SECRET_KEY=generate-with-openssl-rand-hex-32
```

### 2. Start Everything

```bash
docker-compose up --build
```

Wait for all services to start (2-3 minutes first time).

### 3. Initialize Database

In a new terminal:
```bash
docker-compose exec backend alembic upgrade head
```

### 4. Access the Application

- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Backend:** http://localhost:8000

## First Steps

1. **Register an account** at http://localhost:5173/register
2. **Create a project** with your goal
3. **Let AI decompose it** into tasks
4. **Watch for check-ins** (simulated via logs for now)

## Verify Services

```bash
# Check all containers are running
docker-compose ps

# View logs
docker-compose logs -f

# Test API
curl http://localhost:8000/health
```

## Common Commands

```bash
# Stop all services
docker-compose down

# Start in background
docker-compose up -d

# View specific logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Restart a service
docker-compose restart backend

# Rebuild after code changes
docker-compose up --build
```

## Testing the LLM Integration

Create a project via API:
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'

# Login and get token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass123" \
  | jq -r '.access_token')

# Create a project
curl -X POST http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Project",
    "description": "A test project",
    "goal": "Learn the system"
  }'
```

## Troubleshooting

**Services won't start:**
```bash
docker-compose down -v  # Remove volumes
docker-compose up --build
```

**Database errors:**
```bash
docker-compose restart postgres
docker-compose exec backend alembic upgrade head
```

**Can't connect to backend:**
- Check backend logs: `docker-compose logs backend`
- Verify port 8000 is not in use
- Ensure .env file has correct DATABASE_URL

## Next Steps

- Read [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed documentation
- Check [README.md](./README.md) for full project overview
- Start implementing missing frontend pages
- Set up Discord bot for real-time messaging

## Need Help?

- Check container logs: `docker-compose logs -f [service-name]`
- Verify environment variables are set
- Ensure Docker has enough resources (4GB+ RAM recommended)
- Check API docs for endpoint details: http://localhost:8000/docs
