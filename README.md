# 🧠 HiveMind AI

> **Autonomous Multi-Agent Kanban Swarm** — An open-source platform where AI agents collaboratively pick up, execute, and close Kanban tasks in real time.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.121-green?style=flat-square&logo=fastapi)
![AutoGen](https://img.shields.io/badge/AutoGen-0.9-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)
![Deploy on Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=flat-square&logo=render)

---

## 🚀 What is HiveMind AI?

HiveMind AI is a fully autonomous, self-organizing agent swarm built on top of **Microsoft AutoGen** and **FastAPI**. It turns a Kanban board into a live AI workspace — agents poll for open tasks, spin up a multi-agent team (CEO, Data Engineer, Financial Analyst, QA Tester, Risk Manager), execute the task collaboratively, and close the ticket automatically.

**No human in the loop. Pure autonomous execution.**

---

## ✨ Features

- 🤖 **AutoGen GroupChat Swarm** — CEO-led team of 5 specialist agents
- 📋 **Live Kanban Board** — Tasks move from `Backlog → In Progress → Done` in real time
- 🔄 **Sub-task Lifecycle Tracking** — Each agent phase auto-creates and closes its own ticket
- 💬 **Live Comment Feed** — Every agent message is posted as a comment on the ticket
- 🔐 **Authentication** — HTTP Basic Auth with configurable credentials
- ☁️ **One-click Deploy** — Ready-to-deploy on Render with `render.yaml`

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              HiveMind AI Platform            │
│                                             │
│  ┌─────────────┐      ┌──────────────────┐  │
│  │  Kanban UI  │◄────►│  FastAPI Server  │  │
│  │ (public/)   │      │   (server.py)    │  │
│  └─────────────┘      └────────┬─────────┘  │
│                                │             │
│                       ┌────────▼─────────┐  │
│                       │   AutoGen Agent  │  │
│                       │   (agent.py)     │  │
│                       │                  │  │
│                       │  CEO             │  │
│                       │  Data Engineer   │  │
│                       │  Fin. Analyst    │  │
│                       │  QA Tester       │  │
│                       │  Risk Manager    │  │
│                       └──────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
hivemind-ai/
├── server.py           # FastAPI backend — REST API + SQLite + Auth
├── agent.py            # AutoGen swarm agent — polls & executes tasks
├── swarm_server.py     # Swarm orchestration server
├── public/
│   ├── index.html      # Kanban board UI
│   ├── app.js          # Frontend logic & real-time polling
│   └── styles.css      # UI styles
├── swarm_public/
│   └── index.html      # Swarm dashboard view
├── render.yaml         # One-click Render deployment config
├── requirements.txt    # Python dependencies
└── start.sh            # Startup script (runs server + agent together)
```

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.10+
- OpenAI API Key

### 1. Clone the repo
```bash
git clone https://github.com/umang-algo/hivemind-ai.git
cd hivemind-ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
export OPENAI_API_KEY="sk-..."
export ADMIN_USER="admin"
export ADMIN_PASS="yourpassword"
```

### 4. Run the platform
```bash
bash start.sh
```

Visit **http://localhost:8000** for the Kanban board.

---

## ☁️ Deploy on Render

1. Fork this repo
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — just fill in the environment variables:

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `ADMIN_USER` | Login username |
| `ADMIN_PASS` | Login password |

5. Click **Deploy** ✅

---

## 🤖 How the Swarm Works

1. **Agent polls** the Kanban API every 3 seconds for tasks assigned to `agent-autogen`
2. When a task is found, it spins up an **AutoGen GroupChat** with 5 agents
3. Each agent speaks in round-robin — their messages are posted as **live comments** on the ticket
4. Agent handoffs are tracked — **sub-tasks are auto-created and closed** as each phase completes
5. The CEO synthesizes findings and outputs `TERMINATE` to end the session
6. The master ticket is marked **Done** ✅

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLite |
| Agent Framework | Microsoft AutoGen (pyautogen) |
| LLM | OpenAI GPT-4o-mini |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Render |

---

## 📄 License

MIT © [umang-algo](https://github.com/umang-algo)
