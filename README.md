# English Practice Bot

Telegram bot and mini app for repeating English vocabulary.

## Local Docker

Copy environment example:

```powershell
Copy-Item .env.example .env
```

Start services:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Services:

- API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- PgAdmin: `http://localhost:5050`
- Redis: `localhost:6379`
