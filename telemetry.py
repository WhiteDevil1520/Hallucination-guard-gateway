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

class PostgresTelemetryTracker:
    def __init__(self):
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Connects to PostgreSQL and creates the audit_logs table automatically."""
        try:
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
            print(f"⚠️ PostgreSQL connection failed: {e}")
            self.conn = None

    def record(self, item: TelemetryRecord):
        """Inserts a new prompt audit record into PostgreSQL."""
        if not self.conn:
            print("Database not connected. Skipping log.")
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_logs (
                        prompt, response, latency_ms, input_tokens, output_tokens,
                        cost_usd, flagged_injection, flagged_hallucination, fallback_used
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    item.prompt,
                    item.response,
                    item.latency_ms,
                    item.input_tokens,
                    item.output_tokens,
                    item.cost_usd,
                    item.flagged_injection,
                    item.flagged_hallucination,
                    item.fallback_used
                ))
        except Exception as e:
            print(f"Error inserting into PostgreSQL: {e}")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        in_cost = (input_tokens / 1000.0) * settings.cost_per_1k_input
        out_cost = (output_tokens / 1000.0) * settings.cost_per_1k_output
        return in_cost + out_cost

    def get_summary(self) -> Dict:
        """Executes SQL queries to generate metrics for the dashboard."""
        if not self.conn:
            return {"total_requests": 0, "status": "Database disconnected"}

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

                if summary["total_requests"] == 0:
                    return {"total_requests": 0, "status": "No requests logged yet."}

                cur.execute("""
                    SELECT 
                        prompt, 
                        latency_ms, 
                        cost_usd, 
                        flagged_injection AS injection_blocked,
                        flagged_hallucination AS hallucination_intercepted, 
                        fallback_used
                    FROM audit_logs
                    ORDER BY id DESC
                    LIMIT 10;
                """)
                recent_logs = cur.fetchall()

                return {
                    "total_requests": summary["total_requests"],
                    "avg_latency_ms": round(summary["avg_latency_ms"], 2),
                    "total_cost_usd": f"${summary['total_cost_usd']:.6f}",
                    "storage_backend": "PostgreSQL",
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
                        for r in recent_logs
                    ]
                }
        except Exception as e:
            print(f"Error querying PostgreSQL: {e}")
            return {"total_requests": 0, "error": str(e)}

telemetry = PostgresTelemetryTracker()