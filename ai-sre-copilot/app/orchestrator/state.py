"""
Incident State — LangGraph ka shared state
==========================================
Yeh ek TypedDict hai jo poori pipeline mein
ek agent se doosre agent tak travel karta hai.

Har agent is state ko read karta hai aur
apna output isme add kar deta hai.
"""
from typing import TypedDict, Any


class IncidentState(TypedDict):
    # ── Input (Kafka se aata hai) ──────────────
    incident_id:   str
    alert_name:    str
    severity:      str
    labels:        dict          # {"service": "payment-api", "namespace": "prod"}
    annotations:   dict          # {"summary": "...", "description": "..."}
    fired_at:      str

    # ── MetricsAgent output ────────────────────
    metrics_data:  dict          # Prometheus se raw metrics
    metrics_summary: str         # Human readable summary

    # ── LogsAgent output ──────────────────────
    logs_data:     list          # Loki se log lines
    logs_summary:  str           # Error patterns, stack traces

    # ── TracesAgent output ────────────────────
    traces_data:   list          # Tempo se trace spans
    traces_summary: str          # Slow spans, errors

    # ── Evidence Fusion output ────────────────
    fused_evidence: str          # Teeno ka combined summary

    # ── KnowledgeAgent output ─────────────────
    relevant_runbooks: list      # Qdrant se matched runbooks

    # ── RCA Agent output ──────────────────────
    root_cause:    str           # Root cause explanation
    confidence:    float         # 0.0 to 1.0

    # ── Fix Agent output ──────────────────────
    fix_plan:      str           # Step by step fix
    fix_commands:  list          # Actual commands

    # ── Pipeline control ──────────────────────
    current_step:  str           # Kahan hai abhi pipeline
    errors:        list          # Koi bhi agent fail hua?
    retry_count:   int           # Kitni baar retry hua
