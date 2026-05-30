"""
Runbook Ingestion Script
========================
Saare runbooks (Markdown files) ko read karo,
embed karo, aur Qdrant mein store karo.

Run: python scripts/ingest_runbooks.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Project root ko path mein add karo
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)
from sentence_transformers import SentenceTransformer
from app.core.config import settings


def load_runbooks(runbooks_dir: str) -> list[dict]:
    """Saare .md files runbooks/ folder se read karo"""
    runbooks = []
    runbooks_path = Path(runbooks_dir)

    if not runbooks_path.exists():
        print(f"Runbooks directory nahi mili: {runbooks_dir}")
        print("Sample runbooks bana raha hoon...")
        create_sample_runbooks(runbooks_path)

    for md_file in sorted(runbooks_path.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        runbooks.append({
            "id":       md_file.stem,
            "filename": md_file.name,
            "title":    md_file.stem.replace("-", " ").title(),
            "content":  content,
        })
        print(f"  Loaded: {md_file.name} ({len(content)} chars)")

    return runbooks


def create_sample_runbooks(runbooks_path: Path):
    """Agar runbooks nahi hain to sample bana do"""
    runbooks_path.mkdir(exist_ok=True)

    samples = {
        "high-cpu.md": """# High CPU Usage Runbook

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
""",
        "oom-kill.md": """# OOM Kill Runbook

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
""",
        "service-down.md": """# Service Down Runbook

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
""",
    }

    for filename, content in samples.items():
        (runbooks_path / filename).write_text(content)
        print(f"  Created sample: {filename}")


def ingest_to_qdrant(runbooks: list[dict]):
    """Runbooks ko embed karke Qdrant mein save karo"""

    # Embedding model load karo
    print("\nEmbedding model load ho raha hai (pehli baar slow hoga)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Qdrant client
    client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    # Collection create karo (agar nahi hai)
    collections = [c.name for c in client.get_collections().collections]

    if settings.QDRANT_COLLECTION not in collections:
        print(f"Collection '{settings.QDRANT_COLLECTION}' bana raha hoon...")
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.QDRANT_VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
    else:
        print(f"Collection '{settings.QDRANT_COLLECTION}' already exists")

    # Embed aur upsert
    print(f"\n{len(runbooks)} runbooks index ho rahi hain...")
    points = []

    for i, rb in enumerate(runbooks):
        embedding = model.encode(rb["content"]).tolist()
        points.append(
            PointStruct(
                id=i + 1,
                vector=embedding,
                payload={
                    "id":       rb["id"],
                    "title":    rb["title"],
                    "filename": rb["filename"],
                    "content":  rb["content"],
                },
            )
        )
        print(f"  [{i+1}/{len(runbooks)}] Embedded: {rb['title']}")

    client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    print(f"\nDone! {len(points)} runbooks indexed in Qdrant.")
    print(f"Dashboard: http://localhost:6333/dashboard")


if __name__ == "__main__":
    runbooks_dir = Path(__file__).parent.parent / "runbooks"
    print("=== Runbook Ingestion ===")
    print(f"Directory: {runbooks_dir}\n")

    runbooks = load_runbooks(str(runbooks_dir))
    if not runbooks:
        print("Koi runbook nahi mila!")
        sys.exit(1)

    print(f"\n{len(runbooks)} runbooks mili")
    ingest_to_qdrant(runbooks)
