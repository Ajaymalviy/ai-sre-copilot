# Service Down Runbook

## Symptoms
- Health check failing
- 5xx errors spike
- Prometheus target down

## Investigation Steps
1. Check pod status: `kubectl get pods -n <namespace>`
2. Check pod logs: `kubectl logs <pod-name> --previous`
3. Check node status: `kubectl get nodes`
4. Check recent events: `kubectl get events --sort-by='.lastTimestamp'`

## Fix Steps
1. Restart deployment: `kubectl rollout restart deployment/<name>`
2. If node issue: drain and cordon node
3. If config issue: check ConfigMap and Secrets

## Prevention
- Liveness and readiness probes
- Multi-replica deployments
- PodDisruptionBudget
