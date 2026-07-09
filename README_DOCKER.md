# Running PathPilot with Docker

This guide details how to spin up PathPilot along with a local, persistent PostgreSQL instance using Docker and Docker Compose.

---

## Prerequisites
Ensure you have the following installed on your system:
- **Docker Desktop** (or Docker Engine)
- **Docker Compose** (typically included with Docker Desktop)

---

## Configuration

If you want to configure third-party LLM provider API keys inside the container, you can copy the `.env.example` file to `.env` in the root directory:
```bash
cp .env.example .env
```
And open `.env` to define your API keys:
- `GEMINI_API_KEY` (or other LLM variables)

The `docker-compose.yml` mounts the `.env` settings or passes environment variables directly.

---

## Commands

### 1. Build and Start the Services
Run the following command in the project root to build the Streamlit image and spin up the database and web app:
```bash
docker compose up --build
```
This command:
* Compiles the Dockerfile environment.
* Boots a PostgreSQL database container on port `5432`.
* Automatically runs the database schemas bootstrap.
* Exposes PathPilot on port `8501`.

Once launched, you can open your browser and navigate to:
👉 **[http://localhost:8501](http://localhost:8501)**

### 2. Stop the Services
To stop the services and stop the containers (while keeping database volumes safe):
```bash
docker compose down
```

### 3. Clear Database Volumes (Hard Reset)
If you want to completely erase the database volume and start fresh:
```bash
docker compose down -v
```

---

## Directory Mappings
* **Outputs**: The local `./outputs` directory is mounted into the container at `/app/outputs`. All generated PDF resumes, cover letters, and logs will be immediately accessible on your host machine.
* **Database Data**: PostgreSQL files are stored inside a managed Docker volume named `postgres_data`, keeping your profiles, user credentials, and applications safe even if you stop or rebuild the container.
