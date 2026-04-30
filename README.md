# Rapid Research Reasoner
## Conventions 
- All services use FastAPI
- All sync communications use REST
- All async communications use RabbitMQ
- All data contracts are pydantic models in /shared

## Local thin-slice flow

For a full step-by-step startup guide, see
[docs/run-locally.md](docs/run-locally.md).

```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000/healthz
- RabbitMQ management: http://localhost:15672

The frontend submits `multipart/form-data` to `POST /chat/jobs`, the API stores
PDFs under `services/data`, RabbitMQ queues the job, and the worker writes
completed retrieval results back to PostgreSQL.

## Kubernetes

```bash
helm lint infra/helm/rrr
helm template rrr infra/helm/rrr -f infra/helm/rrr/values-minikube.yaml
./scripts/minikube-smoke.sh
```

Update `infra/helm/rrr/values-minikube.yaml` with the GHCR image repositories
for your fork before syncing through ArgoCD.
