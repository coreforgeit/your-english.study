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

## Production Docker Deploy

GitHub Actions builds API, bot, and frontend images and pushes them to GitHub Container Registry.
The server only needs Docker, Docker Compose, and this deploy layout:

```text
/opt/english_practice_bot/
  .deploy.env
  docker/
    docker-compose.prod.yml
    Caddyfile
```

The workflow writes `.env` from the `APP_ENV` environment secret and `.deploy.env` with the image tags from the current commit.

Required GitHub Actions secrets:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PATH`, for example `/opt/english_practice_bot`
- `APP_ENV`, full production `.env` content
- `GHCR_USERNAME`
- `GHCR_TOKEN` with `read:packages`

Optional GitHub Actions secret:

- `DEPLOY_PORT`, defaults to `22`

Required GitHub Actions variables:

- `VITE_API_URL`, for example `https://api.your-english.study`
- `VITE_FRONTEND_URL`, for example `https://app.your-english.study`
