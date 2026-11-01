import os
import time
from dataclasses import dataclass, asdict
from typing import List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings

@dataclass
class TelemetryRecord:
    timestamp: float
    prompt: str
    response: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    flagged_injection: bool = False
    flagged_hallucination: bool = False
    fallback_used: bool = False
    abstained: bool = False
    calibrated_score: float = 0.0

class ResilientTelemetryTracker:
    def __init__(self):
        self.conn = None
        self.memory_records: List[TelemetryRecord] = []
        self._connect_db()

    def _clean_db_url(self, raw_url: str) -> str:
        if not raw_url:
            return ""
        url = raw_url.strip()
        if url.startswith("psql"):
            url = url[4:].strip()
        url = url.strip("'\"")
        if url and "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
        return url

    def _connect_db(self):
        raw_url = getattr(settings, "database_url", "") or os.getenv("DATABASE_URL", "")
        db_url = self._clean_db_url(raw_url)
        try:
            if db_url:
                self.conn = psycopg2.connect(db_url)
            else:
                self.conn = psycopg2.connect(
                    host=settings.db_host,
                    port=settings.db_port,
                    dbname=settings.db_name,
                    user=settings.db_user,
                    password=settings.db_password
                )
            self.conn.autocommit = True
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        prompt TEXT NOT NULL,
                        response TEXT NOT NULL,
                        latency_ms DOUBLE PRECISION NOT NULL,
                        input_tokens INT NOT NULL,
                        output_tokens INT NOT NULL,
                        cost_usd DOUBLE PRECISION NOT NULL,
                        flagged_injection BOOLEAN DEFAULT FALSE,
                        flagged_hallucination BOOLEAN DEFAULT FALSE,
                        fallback_used BOOLEAN DEFAULT FALSE,
                        abstained BOOLEAN DEFAULT FALSE,
                        calibrated_score DOUBLE PRECISION DEFAULT 0.0
                    );
                """)
            print("✅ Successfully connected to PostgreSQL! Table 'audit_logs' verified.")
        except Exception as e:
            print(f"⚠️ PostgreSQL not connected ({e}). Using in-memory buffer.")
            self.conn = None

    def record(self, item: TelemetryRecord):
        self.memory_records.append(item)
        if not self.conn or self.conn.closed:
            self._connect_db()

        if self.conn and not self.conn.closed:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO audit_logs (
                            prompt, response, latency_ms, input_tokens, output_tokens,
                            cost_usd, flagged_injection, flagged_hallucination, fallback_used,
                            abstained, calibrated_score
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        item.prompt, item.response, item.latency_ms, item.input_tokens,
                        item.output_tokens, item.cost_usd, item.flagged_injection,
                        item.flagged_hallucination, item.fallback_used, item.abstained,
                        item.calibrated_score
                    ))
            except Exception as e:
                print(f"⚠️ Insert failed: {e}. Saved in memory.")
                self.conn = None

    def calculate_cost(self, in_tokens: int, out_tokens: int) -> float:
        return ((in_tokens / 1000.0) * settings.cost_per_1k_input) + ((out_tokens / 1000.0) * settings.cost_per_1k_output)

    def get_summary(self) -> Dict:
        if not self.conn or self.conn.closed:
            self._connect_db()

        if self.conn and not self.conn.closed:
            try:
                with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) AS total_requests,
                            COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                            COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                            COALESCE(SUM(CASE WHEN flagged_injection THEN 1 ELSE 0 END), 0) AS injections_blocked,
                            COALESCE(SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END), 0) AS hallucinations_healed,
                            COALESCE(SUM(CASE WHEN abstained THEN 1 ELSE 0 END), 0) AS abstentions
                        FROM audit_logs;
                    """)
                    summary = cur.fetchone()

                    if summary and summary["total_requests"] > 0:
                        cur.execute("""
                            SELECT prompt, latency_ms, cost_usd, 
                                   flagged_injection AS injection_blocked,
                                   fallback_used, abstained, calibrated_score
                            FROM audit_logs
                            ORDER BY id DESC
                            LIMIT 10;
                        """)
                        recent = cur.fetchall()
                        return {
                            "total_requests": summary["total_requests"],
                            "avg_latency_ms": round(summary["avg_latency_ms"], 2),
                            "total_cost_usd": f"${summary['total_cost_usd']:.6f}",
                            "storage_backend": "PostgreSQL (Neon Cloud)",
                            "security_metrics": {
                                "injections_blocked": summary["injections_blocked"],
                                "hallucinations_healed": summary["hallucinations_healed"],
                                "abstentions": summary["abstentions"]
                            },
                            "recent_logs": [
                                {
                                    "prompt": r["prompt"][:45] + "..." if len(r["prompt"]) > 45 else r["prompt"],
                                    "latency_ms": round(r["latency_ms"], 2),
                                    "cost_usd": f"${r['cost_usd']:.6f}",
                                    "injection_blocked": r["injection_blocked"],
                                    "fallback_used": r["fallback_used"],
                                    "abstained": r["abstained"],
                                    "calibrated_score": r.get("calibrated_score", 0.0)
                                }
                                for r in recent
                            ]
                        }
            except Exception as e:
                print(f"DB read error: {e}")

        # In-Memory fallback
        if not self.memory_records:
            return {"total_requests": 0, "status": "No requests logged yet."}

        total = len(self.memory_records)
        return {
            "total_requests": total,
            "avg_latency_ms": round(sum(r.latency_ms for r in self.memory_records) / total, 2),
            "total_cost_usd": f"${sum(r.cost_usd for r in self.memory_records):.6f}",
            "storage_backend": "In-Memory Buffer",
            "security_metrics": {
                "injections_blocked": sum(1 for r in self.memory_records if r.flagged_injection),
                "hallucinations_healed": sum(1 for r in self.memory_records if r.fallback_used and not r.abstained),
                "abstentions": sum(1 for r in self.memory_records if r.abstained)
            },
            "recent_logs": [
                {
                    "prompt": r.prompt[:45] + "..." if len(r.prompt) > 45 else r.prompt,
                    "latency_ms": round(r.latency_ms, 2),
                    "cost_usd": f"${r.cost_usd:.6f}",
                    "injection_blocked": r.flagged_injection,
                    "fallback_used": r.fallback_used,
                    "abstained": r.abstained,
                    "calibrated_score": r.calibrated_score
                }
                for r in reversed(self.memory_records[-10:])
            ]
        }

telemetry = ResilientTelemetryTracker()