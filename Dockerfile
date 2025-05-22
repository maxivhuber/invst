FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .
RUN uv sync

EXPOSE 8000
ENTRYPOINT ["uv", "run", "gunicorn", "-b", "0.0.0.0:8000", "dash_app:server"]