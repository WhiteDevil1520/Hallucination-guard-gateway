# 🛡️ Hallucination Guard Gateway

An OpenAI-compatible AI gateway and guardrail layer designed to detect and mitigate LLM hallucinations in real-time. It evaluates model confidence, tracks automated refusals, and records full audit logs into **NeonDB (Serverless PostgreSQL)**.

🌐 **Live Gateway:** [Hallucination Guard Gateway](https://hallucination-guard-gateway-1.onrender.com)

---

## ✨ Features

* **OpenAI-Compatible Endpoint:** Drop-in replacement via `/v1/chat/completions`.
* **Hallucination Detection:** Evaluates LLM responses and attaches a `calibrated_score`.
* **Abstention Monitoring:** Tracks when the model refuses to answer (`abstained = true`) due to low confidence or high risk.
* **Persistent Audit Logging:** Automatically logs prompts, completions, tokens, scores, and timestamps directly into **NeonDB**.
* **In-Memory Fallback:** Safely caches logs in memory if the database is temporarily unreachable.

---

## 🛠 Tech Stack

* **Hosting & Deployment:** [Render](https://render.com/) (Web Service)
* **Database:** [NeonDB](https://neon.tech/) (Serverless PostgreSQL)
* **Backend:** Python (FastAPI / Uvicorn)
* **Database Driver:** `psycopg2` / `asyncpg`

---

## ⚙️ Environment Variables

Add these to your **Render Dashboard** under **Environment**:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | NeonDB Connection String (with SSL required) | `postgresql://<user>:<password>@<endpoint>.neon.tech/neondb?sslmode=require` |
| `PORT` | Web server port (Render default is 10000) | `10000` |
| `OPENAI_API_KEY` | Upstream AI Provider API Key | `sk-...` |

---

## 🗄️ Database Schema (NeonDB)

Audit records are saved in the `audit_logs` table inside **NeonDB**:

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model VARCHAR(100),
    prompt TEXT,
    response TEXT,
    calibrated_score FLOAT,
    abstained BOOLEAN DEFAULT FALSE
);
