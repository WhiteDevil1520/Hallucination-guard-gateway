import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from guards import PreFlightGuard, PostFlightGuard
from llm_client import LLMClient
from telemetry import telemetry, TelemetryRecord
from config import settings

app = FastAPI(
    title="Hallucination Guard Gateway",
    description="Zero-trust LLM API proxy protecting against prompt injections and hallucinations.",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    prompt: str = Field(..., example="Explain photosynthesis simply.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

class ChatResponse(BaseModel):
    output: str
    status: str
    guard_report: dict
    latency_ms: float

def build_fallback(reason: str) -> str:
    return (
        f"[GATEWAY FALLBACK]: The primary model's answer was flagged and suppressed "
        f"by the Hallucination Guard. Reason: '{reason}'. Please refine the query context."
    )

@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_gateway(req: ChatRequest):
    start_time = time.time()
    input_tokens = max(1, len(req.prompt.split()) * 2)

    # 1. PRE-FLIGHT CHECK: Block malicious inputs
    is_safe, injection_reason = PreFlightGuard.evaluate(req.prompt)
    if not is_safe:
        elapsed = (time.time() - start_time) * 1000.0
        telemetry.record(TelemetryRecord(
            timestamp=start_time,
            prompt=req.prompt,
            response="[BLOCKED BY PRE-FLIGHT GUARD]",
            latency_ms=elapsed,
            input_tokens=input_tokens,
            output_tokens=0,
            cost_usd=0.0,
            flagged_injection=True
        ))
        raise HTTPException(
            status_code=400,
            detail={"error": "SecurityViolation", "reason": injection_reason}
        )

    # 2. CALL LLM (or mock)
    try:
        raw_response = await LLMClient.generate_response(req.prompt, req.temperature)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM Provider Error: {str(e)}")

    output_tokens = max(1, len(raw_response.split()) * 2)

    # 3. POST-FLIGHT CHECK: Check for hallucination
    is_hallucination, conf, post_reason = PostFlightGuard.evaluate_grounding(req.prompt, raw_response)

    final_output = raw_response
    fallback_engaged = False

    if is_hallucination:
        final_output = build_fallback(post_reason)
        fallback_engaged = True

    # 4. TELEMETRY & COST ACCOUNTING
    elapsed = (time.time() - start_time) * 1000.0
    cost = telemetry.calculate_cost(input_tokens, output_tokens)

    telemetry.record(TelemetryRecord(
        timestamp=start_time,
        prompt=req.prompt,
        response=final_output,
        latency_ms=elapsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        flagged_hallucination=is_hallucination,
        fallback_used=fallback_engaged
    ))

    return ChatResponse(
        output=final_output,
        status="success" if not fallback_engaged else "fallback_engaged",
        guard_report={
            "preflight_passed": True,
            "hallucination_detected": is_hallucination,
            "hallucination_confidence": conf,
            "reason": post_reason
        },
        latency_ms=round(elapsed, 2)
    )

@app.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard():
    """Renders a sleek HTML/CSS visual dashboard."""
    data = telemetry.get_summary()

    if data.get("total_requests", 0) == 0:
        return "<html><body style='background:#0f172a;color:#f8fafc;padding:2rem;'><h2>No requests logged yet. Run <code>python test_gateway.py</code> first!</h2></body></html>"

    rows = ""
    for log in reversed(data.get("recent_logs", [])):
        badge_class = "badge-safe"
        badge_text = "PASSED"
        if log["injection_blocked"]:
            badge_class = "badge-danger"
            badge_text = "INJECTION BLOCKED"
        elif log["hallucination_intercepted"]:
            badge_class = "badge-warning"
            badge_text = "FALLBACK ENGAGED"

        rows += f"""
        <tr>
            <td><code>{log['prompt']}</code></td>
            <td>{log['latency_ms']} ms</td>
            <td>{log['cost_usd']}</td>
            <td><span class="badge {badge_class}">{badge_text}</span></td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Hallucination Guard Dashboard</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
            p.sub {{ color: #94a3b8; margin-bottom: 2rem; }}
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
            .card {{ background: #1e293b; padding: 1.25rem; border-radius: 8px; border: 1px solid #334155; }}
            .card .val {{ font-size: 1.6rem; font-weight: bold; margin-top: 0.25rem; color: #38bdf8; }}
            .card .val.warn {{ color: #f59e0b; }}
            .card .val.danger {{ color: #ef4444; }}
            table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }}
            th, td {{ padding: 0.85rem 1rem; text-align: left; border-bottom: 1px solid #334155; font-size: 0.9rem; }}
            th {{ background: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
            code {{ color: #e2e8f0; font-family: monospace; font-size: 0.85rem; }}
            .badge {{ padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
            .badge-safe {{ background: #064e3b; color: #34d399; }}
            .badge-warning {{ background: #78350f; color: #fbbf24; }}
            .badge-danger {{ background: #7f1d1d; color: #f87171; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Hallucination Guard — Telemetry Dashboard</h1>
            <p class="sub">Real-time edge inspection metrics & security events</p>
            
            <div class="grid">
                <div class="card">
                    <div style="color: #94a3b8; font-size: 0.85rem;">Total Requests</div>
                    <div class="val">{data['total_requests']}</div>
                </div>
                <div class="card">
                    <div style="color: #94a3b8; font-size: 0.85rem;">Avg Latency</div>
                    <div class="val">{data['avg_latency_ms']} ms</div>
                </div>
                <div class="card">
                    <div style="color: #94a3b8; font-size: 0.85rem;">Injections Blocked</div>
                    <div class="val danger">{data['security_metrics']['injections_blocked']}</div>
                </div>
                <div class="card">
                    <div style="color: #94a3b8; font-size: 0.85rem;">Hallucinations Caught</div>
                    <div class="val warn">{data['security_metrics']['hallucinations_detected']}</div>
                </div>
            </div>

            <h2>Recent Request Audit Trail</h2>
            <table>
                <thead>
                    <tr>
                        <th>Prompt</th>
                        <th>Latency</th>
                        <th>Cost</th>
                        <th>Gate Verdict</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mock_mode": settings.mock_mode}