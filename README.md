# 🛡️ Hallucination Guard: Resilient LLM Gateway

A zero-trust API middleware built with FastAPI designed to sit between client apps and Large Language Models. It enforces security pre-flight checks, verifies output factuality post-flight, triggers automatic fallbacks, and tracks token costs and latency in real time.

## 🏗️ Architecture Flow
1. **Client Request** ➡️ **Pre-Flight Guard**: Filters prompt injections, DAN exploits, and jailbreak syntax.
2. **LLM Dispatch**: Forwards safe requests to the model provider (OpenAI / Local).
3. **Post-Flight Guard**: Scans output for hallucinations, contradictions, and fabricated historical claims.
4. **Fallback Engine**: Intercepts ungrounded outputs and replaces them with a safe fallback response.
5. **Telemetry Store**: Audits tokens, latency, and costs via the `/dashboard` endpoint.

## 🚀 Quickstart

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate