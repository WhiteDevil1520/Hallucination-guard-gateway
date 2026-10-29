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

class ResilientTelemetryTracker:
    def __init__(self):
        self.conn = None
        self.memory_records: List[TelemetryRecord] = []
        self._connect_db()

    def _clean_db_url(self, raw_url: str) -> str:
        """Strips out 'psql' prefixes and extra quotes if copied by mistake."""
        if not raw_url:
            return ""
        url = raw_url.strip()
        # If user accidentally copied `psql 'postgresql://...'`
        if url.startswith("psql"):
            url = url[4:].strip()
        # Remove quotes
        url = url.strip("'\"")
        # Ensure sslmode for cloud databases
        if url and "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
        return url

    def _connect_db(self):
        """Attempts to connect to PostgreSQL with SSL support."""
        raw_url = settings.database_url or os.getenv("DATABASE_URL", "")
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
                        fallback_used BOOLEAN DEFAULT FALSE
                    );
                """)
            print("✅ Successfully connected to PostgreSQL! Table 'audit_logs' is ready.")
        except Exception as e:
            print(f"⚠️ PostgreSQL not available ({e}). Using In-Memory buffer.")
            self.conn = None

    def record(self, item: TelemetryRecord):
        """Always stores in memory buffer AND writes to PostgreSQL."""
        # 1. Always save in memory buffer
        self.memory_records.append(item)

        # 2. Reconnect if disconnected
        if not self.conn or self.conn.closed:
            self._connect_db()

        # 3. Write to PostgreSQL
        if self.conn and not self.conn.closed:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO audit_logs (
                            prompt, response, latency_ms, input_tokens, output_tokens,
                            cost_usd, flagged_injection, flagged_hallucination, fallback_used
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        item.prompt, item.response, item.latency_ms, item.input_tokens,
                        item.output_tokens, item.cost_usd, item.flagged_injection,
                        item.flagged_hallucination, item.fallback_used
                    ))
            except Exception as e:
                print(f"⚠️ DB Insert failed ({e}). Retained safely in memory.")
                self.conn = None

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        in_cost = (input_tokens / 1000.0) * settings.cost_per_1k_input
        out_cost = (output_tokens / 1000.0) * settings.cost_per_1k_output
        return in_cost + out_cost

    def get_summary(self) -> Dict:
        """Fetches from PostgreSQL if connected, otherwise uses memory buffer."""
        # Check PostgreSQL
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
                            COALESCE(SUM(CASE WHEN flagged_hallucination THEN 1 ELSE 0 END), 0) AS hallucinations_detected
                        FROM audit_logs;
                    """)
                    summary = cur.fetchone()

                    if summary and summary["total_requests"] > 0:
                        cur.execute("""
                            SELECT prompt, latency_ms, cost_usd, 
                                   flagged_injection AS injection_blocked,
                                   flagged_hallucination AS hallucination_intercepted, 
                                   fallback_used
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
                                "hallucinations_detected": summary["hallucinations_detected"]
                            },
                            "recent_logs": [
                                {
                                    "prompt": r["prompt"][:45] + "..." if len(r["prompt"]) > 45 else r["prompt"],
                                    "latency_ms": round(r["latency_ms"], 2),
                                    "cost_usd": f"${r['cost_usd']:.6f}",
                                    "injection_blocked": r["injection_blocked"],
                                    "hallucination_intercepted": r["hallucination_intercepted"],
                                    "fallback_used": r["fallback_used"]
                                }
                                for r in recent
                            ]
                        }
            except Exception as e:
                print(f"Error reading DB: {e}. Falling back to memory.")

        # Fallback to Memory
        if not self.memory_records:
            return {"total_requests": 0, "status": "No requests logged yet."}

        total_reqs = len(self.memory_records)
        avg_lat = sum(r.latency_ms for r in self.memory_records) / total_reqs
        total_c = sum(r.cost_usd for r in self.memory_records)

        return {
            "total_requests": total_reqs,
            "avg_latency_ms": round(avg_lat, 2),
            "total_cost_usd": f"${total_c:.6f}",
            "storage_backend": "In-Memory Buffer",
            "security_metrics": {
                "injections_blocked": sum(1 for r in self.memory_records if r.flagged_injection),
                "hallucinations_detected": sum(1 for r in self.memory_records if r.flagged_hallucination)
            },
            "recent_logs": [
                {
                    "prompt": r.prompt[:45] + "..." if len(r.prompt) > 45 else r.prompt,
                    "latency_ms": round(r.latency_ms, 2),
                    "cost_usd": f"${r.cost_usd:.6f}",
                    "injection_blocked": r.flagged_injection,
                    "hallucination_intercepted": r.flagged_hallucination,
                    "fallback_used": r.fallback_used
                }
                for r in reversed(self.memory_records[-10:])
            ]
        }

telemetry = ResilientTelemetryTracker()