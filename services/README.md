```bash
uv sync
pre-commit install
uvicorn services.api_gateway.main:app --reload
python -m services.worker.main
```

Required local dependencies:

- PostgreSQL on `localhost:5432`
- RabbitMQ on `localhost:5672`
- `DATA_DIR` defaults to `services/data`
