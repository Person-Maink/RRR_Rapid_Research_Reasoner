# Run The Application Locally

This guide starts the current thin-slice application: React chat frontend,
FastAPI API, RabbitMQ job queue, worker, PostgreSQL, local PDF storage, FAISS
retrieval, and PDF.js citation viewing.

## 1. Prerequisites

Install:

- Docker
- Docker Compose v2 plugin
- Node.js `>=20.19.0` for frontend development

Check your versions:

```bash
node -v
docker --version
docker compose version
```

If you use `nvm`, the repo has `frontend/.nvmrc`:

```bash
nvm install 24.14.1
nvm use 24.14.1
```

## 2. Start The Full Stack

From the repository root:

```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

This starts:

- Frontend: <http://localhost:5173>
- API: <http://localhost:8000>
- RabbitMQ management UI: <http://localhost:15672>
- PostgreSQL on `localhost:5432`
- Worker process for async PDF jobs

RabbitMQ default login:

```text
guest / guest
```

## 3. Confirm The API Is Running

In a second terminal:

```bash
curl http://localhost:8000/healthz
```

Expected response:

```json
{"status":"ok"}
```

## 4. Use The Chat App

Open:

```text
http://localhost:5173
```

Then:

1. Upload one or more PDF files.
2. Enter a question, for example: `What is this paper about?`
3. Click `Send`.
4. Wait for the assistant message to move from `queued` to `processing` to
   `completed`.
5. Inspect the retrieved PDF page in the embedded PDF.js viewer.

## 5. What Works Today

The current implementation performs a real async retrieval flow:

- The frontend submits one multipart request to `POST /chat/jobs`.
- The API saves PDFs under local storage rooted at `services/data`.
- The API creates a PostgreSQL job and enqueues it in RabbitMQ.
- The worker parses PDFs, stores page text, builds FAISS artifacts, retrieves
  relevant pages, and completes the job.
- The frontend polls `GET /chat/jobs/{job_id}` and renders returned PDF pages.

The reasoning answer is still a placeholder template. Ollama is not configured
or required. Retrieval currently uses deterministic local text vectors plus
FAISS, not Ollama embeddings.

## 6. Frontend Development Checks

Use Node `>=20.19.0`:

```bash
cd frontend/frontend
npm install
npm run lint
npm run build
```

If `npm run build` fails with a Vite Node version error, upgrade Node. Vite 8
requires Node `20.19+` or `22.12+`.

## 7. Backend Checks

With `uv` installed:

```bash
cd services
uv sync
uv run ruff check api_gateway ingestion_service reasoning_service retrieval_service worker tests environment.py job_store.py logging_config.py queue.py storage.py vectorize.py ../shared
uv run black --check api_gateway ingestion_service reasoning_service retrieval_service worker tests environment.py job_store.py logging_config.py queue.py storage.py vectorize.py ../shared
uv run pytest
```

Without `uv`, the existing local venv may run part of the suite:

```bash
services/.venv/bin/python -m pytest services/tests
```

The API multipart test requires `python-multipart`; it is installed by
`uv sync`.

## 8. Common Issues

If `docker compose` is not found, install Docker Compose v2. The old
`docker-compose` command may fail on newer Python installations.

If jobs stay queued, check that the worker and RabbitMQ containers are running:

```bash
docker compose -f infra/compose/docker-compose.yml ps
```

If the PDF viewer cannot render a page, open the returned PDF link from the
chat response and check API logs for `GET /documents/{document_id}/pdf`.

If Postgres is slow to start, the API and worker retry DB initialization, but a
fresh compose startup can still take a few seconds.

## 9. Optional Minikube Path

After Docker Compose works, validate Kubernetes manifests:

```bash
helm lint infra/helm/rrr
helm template rrr infra/helm/rrr -f infra/helm/rrr/values-minikube.yaml
```

Then run the smoke helper:

```bash
./scripts/minikube-smoke.sh
```

Update the placeholder GHCR image repositories and ArgoCD repo URL before using
the ArgoCD application manifest for real sync.
