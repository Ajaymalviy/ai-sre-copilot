# High CPU Usage Runbook

## Symptoms
- CPU usage > 80% for more than 2 minutes
- Application response time increasing
- Load average spike

## Investigation Steps
1. Check which process is consuming CPU: `top` or `htop`
2. Check Kubernetes pod CPU: `kubectl top pods -n <namespace>`
3. Check recent deployments: `kubectl rollout history deployment/<name>`
4. Look for infinite loops in logs: query Loki for error patterns

## Common Causes
- Infinite loop in application code
- Memory leak causing GC pressure
- Sudden traffic spike
- Background job running wild

## Fix Steps
1. If recent deployment: `kubectl rollout undo deployment/<name>`
2. If traffic spike: scale up pods `kubectl scale deployment/<name> --replicas=5`
3. If specific pod: `kubectl delete pod <pod-name>` (it will restart)
4. Add HPA if not present: horizontal pod autoscaler

## Prevention
- Set resource limits in pod spec
- Configure HPA for auto-scaling
- Add CPU usage alerts at 70% threshold
