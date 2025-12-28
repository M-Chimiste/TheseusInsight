# Docker Setup Guide for Theseus Insight

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TheseusInsight
   ```

2. **Set up environment variables**
   ```bash
   # Copy the example environment file
   cp env.example .env
   
   # IMPORTANT: Edit .env and configure:
   # - Comment out or remove DATABASE_URL line (Docker will use its own)
   # - Add your API keys (OPENAI_API_KEY, etc.)
   ```

3. **Start the application**
   ```bash
   docker-compose up --build
   ```

   The application will be available at http://localhost:8000

## Troubleshooting

### Database Connection Errors

If you see errors like:
- `Temporary failure in name resolution`
- `Name or service not known`
- `Connection pool timeout`

**Solution:**
1. Make sure DATABASE_URL is NOT set in your `.env` file (comment it out or remove it)
2. The docker-compose.yml file sets the correct DATABASE_URL automatically
3. If DATABASE_URL is in your .env file, it overrides the Docker setting and causes connection failures

### Correct Database URLs

- **For Docker Compose:** `postgresql://theseus:theseus@db:5432/theseusdb` (automatically set)
- **For local development:** `postgresql://postgres:postgres@localhost:5432/theseus`

### Checking Container Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View database logs specifically
docker-compose logs -f db

# View app logs specifically
docker-compose logs -f theseus-insight-app
```

### Rebuilding After Changes

```bash
# Stop and remove containers
docker-compose down

# Rebuild and start
docker-compose up --build
```

### Database Persistence

Database data is stored in a Docker volume and persists between container restarts.
To completely reset the database:

```bash
# Warning: This will delete all data!
docker-compose down -v
docker-compose up --build
```

## Ollama Configuration for Docker

If you want to use Ollama models from the host machine:

1. Make sure Ollama is running on your host machine
2. Set `OLLAMA_PASSTHROUGH=true` in your `.env` file (default)
3. The Docker container will redirect Ollama requests to your host machine

If you want to run Ollama inside Docker:
1. Set `OLLAMA_PASSTHROUGH=false` in your `.env` file
2. You'll need to set up Ollama inside the container (not covered here)

## Network Configuration

The Docker Compose setup creates an internal network where:
- The app container can reach the database at hostname `db`
- The database is NOT exposed to your host machine (for security)
- Only the app's port 8000 is exposed to your host

## Environment Variables Priority

1. docker-compose.yml `environment:` section (highest priority)
2. .env file
3. System environment variables (lowest priority)

This is why DATABASE_URL in .env must be commented out - it would override the Docker setting.