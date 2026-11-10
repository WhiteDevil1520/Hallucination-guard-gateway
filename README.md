# 🚀 Project Name

Brief description of what your app does (e.g., An AI proxy service with audit logging and calibrated scoring).

🌐 **Live URL:** [https://your-service-name.onrender.com](https://your-service-name.onrender.com)

---

## 🛠 Tech Stack

* **Hosting:** [Render](https://render.com/)
* **Database:** [Neon PostgreSQL](https://neon.tech/)
* **Backend:** Python (FastAPI / Flask) <!-- Or Node.js / Express -->
* **AI Provider:** OpenAI / Gemini / etc.

---

## ⚙️ Environment Variables

To run this project, configure the following environment variables in your Render Dashboard (**Settings → Environment Variables**):

| Variable | Description | Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | Neon Postgres Connection String | `postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` |
| `PORT` | Port for the web server (Render defaults to 10000) | `10000` |
| `API_KEY` | Your AI API Key (if applicable) | `sk-...` |

---

## 🚀 Deployment on Render

Follow these steps to deploy this repository to Render:

1. **Fork or Push** this repository to your GitHub account.
2. Sign up / Log in to [Render](https://dashboard.render.com/).
3. Click **New +** → **Web Service**.
4. Connect your GitHub repository.
5. Set the service settings:
   * **Runtime:** `Python 3` *(or `Node`)*
   * **Build Command:** `pip install -r requirements.txt` *(or `npm install`)*
   * **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT` *(replace with your actual start command)*
   * **Instance Type:** `Free`
6. Under **Environment Variables**, add your `DATABASE_URL` from your Neon project.
7. Click **Deploy Web Service**.

> ⚠️ **Note on Free Tier Inactivity:** Render free instances spin down after 15 minutes of inactivity. The first request after sleep may take ~30–50 seconds to respond.

---

## 🗄️ Database Setup (Neon)

This project uses **Neon Serverless PostgreSQL**.

1. Create a free account at [neon.tech](https://neon.tech).
2. Create a project and database.
3. Copy the **Pooled Connection String** from the Neon dashboard.
4. Paste it as the `DATABASE_URL` in Render.
5. Tables are automatically initialized on startup.

---

## 💻 Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/your-repo-name.git
   cd your-repo-name
