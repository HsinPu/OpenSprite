FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM frontend-build AS frontend-test
# Bound workers to avoid CPU contention in Docker Desktop's shared VM.
RUN npm test -- --run --maxWorkers=2 && npm run typecheck

FROM python:3.12-slim-bookworm AS backend-build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
# MCP stdio requires an absolute executable that is not a symbolic link.
RUN python -m venv --copies --without-pip .venv \
    && uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --locked --no-dev

FROM backend-build AS backend-test
COPY backend/tests ./tests
COPY installers /app/installers
COPY contracts /app/contracts
COPY scripts /app/scripts
COPY docs /app/docs
COPY README.md AGENTS.md /app/
RUN uv sync --locked --dev \
    && uv run pytest -W error \
    && uv run python -m compileall -q src tests \
    && uv lock --check --offline \
    && uv pip check

FROM python:3.12-slim-bookworm AS runtime
ENV HOME=/home/opensprite \
    OPENSPRITE_RUNTIME_KIND=docker \
    PATH=/app/backend/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 opensprite \
    && useradd --uid 10001 --gid opensprite --create-home opensprite \
    && install -d -m 700 -o opensprite -g opensprite /home/opensprite/.opensprite /home/opensprite/.opensprite/config \
    && printf '{"version":1,"mode":"trusted_local"}\n' > /home/opensprite/.opensprite/config/access-policy.json \
    && chown opensprite:opensprite /home/opensprite/.opensprite/config/access-policy.json \
    && chmod 600 /home/opensprite/.opensprite/config/access-policy.json
WORKDIR /app/backend
COPY --from=backend-build /app/backend /app/backend
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
USER opensprite
EXPOSE 8765
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; import json; assert json.load(urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=4)) == {'status': 'ok'}"
CMD ["uvicorn", "opensprite_backend.installed_runtime:create_installed_app", "--factory", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--no-proxy-headers"]
