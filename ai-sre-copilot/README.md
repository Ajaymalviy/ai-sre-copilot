# AI SRE Copilot

Automated incident investigation platform — alerts se lekar root cause tak, bina AI ke abhi.

---

## Prerequisites

```bash
# Yeh sab installed hona chahiye
docker --version        # Docker 24+
docker compose version  # Docker Compose v2
python3 --version       # Python 3.11+
```

---

## Quick Start (Scratch se)

### Step 1 — Project clone ya copy karo

```bash
cd ai-sre-copilot
```

### Step 2 — Infra start karo

```bash
cd infra
docker compose up -d
```

Kya start hoga:
| Service | Port | Purpose |
|---|---|---|
| Kafka | 9092 | Alert event bus |
| Zookeeper | 2181 | Kafka ki zaroorat |
| PostgreSQL | 5432 | Incident storage |
| Redis | 6379 | Cache + HITL state |
| Qdrant | 6333 | Vector DB (runbooks) |
| Prometheus | 9090 | Metrics |
| AlertManager | 9093 | Alert routing |
| Loki | 3100 | Log aggregation |
| Tempo | 3200, 4317, 4318 | Distributed traces |
| Grafana | 3000 | Dashboards |

### Step 3 — Services healthy hone ka check karo

```bash
# Sab containers running hain?
docker compose ps

# Kafka topics bane ki nahi?
docker compose exec kafka kafka-topics --bootstrap-server localhost:29092 --list

# PostgreSQL connected?
docker compose exec postgres psql -U sre_user -d sre_copilot -c "\dt"
```

### Step 4 — Python environment setup

```bash
cd ..  # project root pe jao
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Step 5 — .env file

```bash
cp .env.example .env
# .env open karo aur apni values daalo (abhi default chalega local ke liye)
```

### Step 6 — Runbooks index karo (Qdrant mein)

```bash
python scripts/ingest_runbooks.py
```

### Step 7 — FastAPI app start karo

```bash
uvicorn main:app --reload --port 8000
```

### Step 8 — Test karo

```bash
# Health check
curl http://localhost:8000/health

# Test alert bhejo
curl -X POST http://localhost:8000/webhook/test-alert \
  -H 'Content-Type: application/json' \
  -d '{"alertname": "HighCPUUsage", "severity": "warning"}'

# Incidents dekho
curl http://localhost:8000/api/v1/incidents

# API docs
open http://localhost:8000/docs
```

---

## Grafana Access

URL: http://localhost:3000
Login: `admin` / `admin123`

Datasources auto-configured hain:
- Prometheus (metrics)
- Loki (logs)
- Tempo (traces)

---

## Project Structure

```
ai-sre-copilot/
├── infra/
│   ├── docker-compose.yml      ← Sab services yahan hain
│   ├── postgres/init.sql       ← DB schema
│   ├── prometheus/
│   │   ├── prometheus.yml      ← Scrape config
│   │   ├── alerts.yml          ← Alert rules
│   │   └── alertmanager.yml    ← Routing config
│   ├── loki/                   ← Log config
│   ├── tempo/                  ← Trace config
│   └── grafana/                ← Dashboard config
│
├── app/
│   ├── core/
│   │   ├── config.py           ← Settings (.env)
│   │   └── logging.py          ← Structured logs
│   ├── db/
│   │   └── session.py          ← PostgreSQL async
│   ├── kafka/
│   │   └── consumer.py         ← Alert listener
│   ├── models/
│   │   └── incident.py         ← SQLAlchemy model
│   └── api/
│       ├── routes.py           ← REST endpoints
│       └── webhook.py          ← AlertManager webhook
│
├── scripts/
│   ├── start.sh                ← One-click start
│   └── ingest_runbooks.py      ← Qdrant indexing
│
├── runbooks/                   ← Markdown runbooks yahan rakhna
├── main.py                     ← FastAPI entry point
├── requirements.txt
└── .env.example
```

---

## Next Steps (Agle Phases)

- [ ] Phase 3: LangGraph agent pipeline (MetricsAgent, LogsAgent, TracesAgent)
- [ ] Phase 4: RCA Agent (Ollama + Qwen)
- [ ] Phase 5: HITL approval gate
- [ ] Phase 6: Slack + Jira integration

---

## Troubleshooting

**Kafka connection refused:**
```bash
docker compose logs kafka | tail -20
# Zookeeper healthy hone ka wait karo
```

**PostgreSQL auth failed:**
```bash
# .env mein DATABASE_URL check karo
docker compose exec postgres psql -U sre_user -d sre_copilot
```

**Qdrant not reachable:**
```bash
curl http://localhost:6333/healthz
docker compose logs qdrant
```
