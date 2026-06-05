# OOM Kill Runbook

## Symptoms
- Pod status: OOMKilled
- Memory usage spike before kill
- Application suddenly unavailable

## Investigation Steps
1. Check pod events: `kubectl describe pod <pod-name>`
2. Look for OOMKilled in events: `kubectl get events --field-selector reason=OOMKilling`
3. Check memory limits: `kubectl get pod <pod> -o yaml | grep -A5 resources`
4. Query logs before crash: Loki query `{container="<name>"} |= "OutOfMemory"`

## Common Causes
- Memory limit too low
- Memory leak in application
- Large dataset loaded into memory
- Cache not being evicted

## Fix Steps
1. Increase memory limit in deployment yaml
2. If memory leak: rollback to previous version
3. Add memory profiling to application
4. Review cache eviction policies

## Prevention
- Set memory requests = 50% of limits
- Enable memory usage alerts at 85%
- Regular heap dump analysis in staging
