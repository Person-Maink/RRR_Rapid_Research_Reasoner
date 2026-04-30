# Observability Thin Slice

This folder contains a local Minikube ELK setup for log discovery.

```bash
kubectl create namespace observability
kubectl apply -n observability -f elasticsearch-kibana.yaml
kubectl apply -n observability -f filebeat-daemonset.yaml
kubectl port-forward -n observability svc/kibana 5601:5601
```

Filebeat reads Kubernetes container logs and ships them to Elasticsearch. The API
and worker emit JSON logs, so Kibana can filter on fields such as `service`,
`job_id`, `status`, and `duration_ms`.
