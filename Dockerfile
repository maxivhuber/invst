FROM python:3.12-slim-bookworm:latest

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .
RUN uv sync
CMD ["uv", "run", "dash_app.py"]
