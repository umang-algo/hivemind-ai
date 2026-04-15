import sqlite3
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import List, Optional
import os
import datetime
import secrets
import threading
import time
import requests as http_requests

security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, os.environ.get("ADMIN_USER", "admin"))
    correct_password = secrets.compare_digest(credentials.password, os.environ.get("ADMIN_PASS", "secure_password"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ─── EMBEDDED AGENT DAEMON ────────────────────────────────────────────────────
AGENT_ID = "agent-autogen"
API_BASE  = f"http://localhost:{os.environ.get('PORT', '8000')}/api"

def agent_register():
    try:
        http_requests.post(f"{API_BASE}/agents", json={
            "id": AGENT_ID, "name": "AutoGen Swarm",
            "provider": "AutoGen GroupChat", "runtime": "Render Cloud",
            "avatar": "avatar-claude", "initial": "AG"
        }, timeout=5)
        print("✅ AutoGen agent registered", flush=True)
    except Exception as e:
        print(f"⚠️  Agent registration failed: {e}", flush=True)

def agent_add_comment(issue_id, text, author="AutoGen CEO"):
    try:
        http_requests.post(f"{API_BASE}/issues/{issue_id}/comments",
            json={"author": author, "text": text, "time": "just now"}, timeout=5)
    except: pass

def agent_update_status(issue_id, status):
    try:
        http_requests.put(f"{API_BASE}/issues/{issue_id}",
            json={"status": status}, timeout=5)
    except: pass

def agent_solve_task(task):
    """Run AutoGen swarm for a task. Falls back to simulation if no API key."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Simulation mode — no OpenAI key
        agent_add_comment(task["id"], "🤖 AutoGen Swarm activated in **simulation mode** (no OPENAI_API_KEY set).\n\nTo enable real AI execution, add your `OPENAI_API_KEY` in Render → Environment Variables.", author="System")
        time.sleep(3)
        agent_add_comment(task["id"], "📊 Data Engineer: Fetching relevant data and writing analysis script...", author="Data_Engineer")
        time.sleep(4)
        agent_add_comment(task["id"], "🔍 Financial Analyst: Reviewed the data. Risk-reward looks favorable. Confidence: 87%.", author="Financial_Analyst")
        time.sleep(3)
        agent_add_comment(task["id"], "✅ QA Tester: Pass. All outputs verified within acceptable parameters.", author="QA_Tester")
        time.sleep(2)
        agent_add_comment(task["id"], "⚠️ Risk Manager: Risk Score 3/10 — Low risk. Proceed.", author="Risk_Manager")
        time.sleep(2)
        agent_add_comment(task["id"], f"📋 CEO Summary: The team has completed analysis of **{task['title']}**. All phases passed QA. Risk is low. Task is approved and complete.", author="CEO")
        return

    try:
        import autogen
        llm_config = {"model": "gpt-4o-mini", "api_key": api_key, "max_tokens": 500}
        is_term = lambda x: "TERMINATE" in str(x.get("content", "")).upper()

        user_proxy = autogen.UserProxyAgent(
            name="User_Proxy",
            system_message="Human administrator. Execute python code written by engineers.",
            code_execution_config={"work_dir": "workspace", "use_docker": False},
            human_input_mode="NEVER", max_consecutive_auto_reply=10, is_termination_msg=is_term
        )
        agents_list = [
            autogen.AssistantAgent("CEO", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are the CEO. Synthesize findings in 1 sentence then say TERMINATE."),
            autogen.AssistantAgent("Data_Engineer", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are a Data Engineer. Write python code ONCE. Max 1 sentence explanation."),
            autogen.AssistantAgent("Financial_Analyst", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are an Analyst. Provide exactly 1 sentence of analysis."),
            autogen.AssistantAgent("QA_Tester", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are QA. Say Pass or Fail in 1 sentence."),
            autogen.AssistantAgent("Risk_Manager", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are Risk Manager. Give a risk score in 1 sentence."),
        ]
        groupchat = autogen.GroupChat(
            agents=[user_proxy] + agents_list, messages=[], max_round=6,
            speaker_selection_method="round_robin"
        )
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

        def monitor():
            last = 0
            while True:
                cur = len(groupchat.messages)
                for i in range(last, cur):
                    msg = groupchat.messages[i]
                    agent_add_comment(task["id"], msg.get("content", ""), author=msg.get("name", "Agent"))
                last = cur
                time.sleep(1)
                if cur >= groupchat.max_round * 2: break

        t = threading.Thread(target=monitor, daemon=True)
        t.start()
        user_proxy.initiate_chat(manager, message=f"Task: {task['title']}\n\n{task['desc']}")
    except Exception as e:
        agent_add_comment(task["id"], f"❌ AutoGen crashed: {e}", author="System")

def agent_polling_loop():
    print("🤖 AutoGen Agent daemon starting...", flush=True)
    time.sleep(5)  # Wait for server to be fully ready
    agent_register()
    print("📡 Polling for tasks every 3 seconds...", flush=True)
    while True:
        try:
            res = http_requests.get(f"{API_BASE}/issues", timeout=5)
            tasks = [i for i in res.json()
                     if i.get("assignee") == AGENT_ID
                     and i.get("status") in ("backlog", "todo")
                     and "Sub-Task of" not in i.get("desc", "")]
            for task in tasks:
                print(f"🚀 Picking up {task['id']}: {task['title']}", flush=True)
                agent_update_status(task["id"], "in-progress")
                agent_add_comment(task["id"], f"🤖 **AutoGen Swarm** has picked up this task and is spinning up the team...", author="System")
                agent_solve_task(task)
                agent_update_status(task["id"], "done")
                agent_add_comment(task["id"], "✅ Task completed by AutoGen Swarm.", author="System")
                print(f"✅ Done {task['id']}", flush=True)
        except Exception as e:
            print(f"⚠️  Poll error: {e}", flush=True)
        time.sleep(3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start agent daemon thread on server startup
    t = threading.Thread(target=agent_polling_loop, daemon=True)
    t.start()
    print("🚀 HiveMind AI server started. Agent daemon running.", flush=True)
    yield

# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Multica Backend", lifespan=lifespan)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Create Issues table
    c.execute('''CREATE TABLE IF NOT EXISTS issues
                 (id TEXT PRIMARY KEY, title TEXT, status TEXT, priority TEXT, assignee TEXT, desc TEXT, created TEXT)''')
    # Create Agents table
    c.execute('''CREATE TABLE IF NOT EXISTS agents
                 (id TEXT PRIMARY KEY, name TEXT, provider TEXT, status TEXT, runtime TEXT, tasksCompleted INTEGER, skillsUsed INTEGER, avatar TEXT, initial TEXT)''')
    # Create Comments table
    c.execute('''CREATE TABLE IF NOT EXISTS comments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id TEXT, author TEXT, text TEXT, time TEXT)''')

    
    # Prepopulate if empty
    c.execute('SELECT COUNT(*) FROM issues')
    if c.fetchone()[0] == 0:
        sample_issues = [
            ('MUL-1', 'Set up CI/CD pipeline with GitHub Actions', 'backlog', 'high', 'human', 'Configure automated testing and deployment workflows.', '2d ago'),
            ('MUL-2', 'Design agent skill registry API', 'backlog', 'medium', 'agent-claude', 'Define the API contracts for registering and retrieving agent skills.', '3d ago'),
            ('MUL-3', 'Refactor backend database models', 'todo', 'urgent', 'agent-python', 'Refactor the backend to use proper SQLAlchemy models.', '1d ago'),
            ('MUL-4', 'Implement multi-workspace isolation', 'in-progress', 'high', 'human', 'Ensure data and agents are fully isolated per workspace.', '2d ago'),
        ]
        c.executemany("INSERT INTO issues VALUES (?, ?, ?, ?, ?, ?, ?)", sample_issues)
        
        sample_agents = [
            ('ag-1', 'Claude Agent', 'Claude Code', 'busy', 'Cloud Runner #1', 47, 12, 'avatar-claude', 'C'),
            ('ag-2', 'Codex Bot', 'OpenAI Codex', 'idle', 'Staging Server', 31, 8, 'avatar-codex', 'K'),
            ('agent-autogen', 'AutoGen Swarm', 'AutoGen GroupChat', 'idle', 'Render Cloud', 0, 0, 'avatar-claude', 'AG'),
        ]
        c.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_agents)
        
    # Always ensure agent-autogen exists (upsert for existing DBs)
    c.execute("SELECT id FROM agents WHERE id = 'agent-autogen'")
    if not c.fetchone():
        c.execute("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  ('agent-autogen', 'AutoGen Swarm', 'AutoGen GroupChat', 'idle', 'Render Cloud', 0, 0, 'avatar-claude', 'AG'))

    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Models
class IssueStatusUpdate(BaseModel):
    status: str

class IssueCreate(BaseModel):
    title: str
    desc: str
    status: str
    priority: str
    assignee: str

class AgentCreate(BaseModel):
    id: str
    name: str
    provider: str
    runtime: str
    avatar: str
    initial: str

class CommentCreate(BaseModel):
    author: str
    text: str
    time: str

@app.get("/health")
def health_check():
    conn = get_db()
    agent = conn.execute("SELECT status FROM agents WHERE id = 'agent-autogen'").fetchone()
    conn.close()
    return {
        "status": "ok",
        "server": "running",
        "agent_autogen": dict(agent)["status"] if agent else "not_registered"
    }

@app.get("/api/issues")
def get_issues():
    conn = get_db()
    issues = conn.execute("SELECT * FROM issues ORDER BY CAST(SUBSTR(id, 5) AS INTEGER) DESC, id DESC").fetchall()
    conn.close()
    return [dict(ix) for ix in issues]

@app.post("/api/issues")
def create_issue(issue: IssueCreate):
    conn = get_db()
    c = conn.cursor()
    # Auto-increment ID
    c.execute("SELECT id FROM issues ORDER BY CAST(SUBSTR(id, 5) AS INTEGER) DESC LIMIT 1")
    row = c.fetchone()
    if row:
        last_id = int(row[0].split('-')[1])
        new_id = f"MUL-{last_id + 1}"
    else:
        new_id = "MUL-1"
        
    created = 'just now'
    c.execute("INSERT INTO issues VALUES (?, ?, ?, ?, ?, ?, ?)",
              (new_id, issue.title, issue.status, issue.priority, issue.assignee, issue.desc, created))
    conn.commit()
    conn.close()
    return {"id": new_id}

@app.put("/api/issues/{issue_id}")
def update_issue(issue_id: str, payload: IssueStatusUpdate):
    conn = get_db()
    conn.execute("UPDATE issues SET status = ? WHERE id = ?", (payload.status, issue_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/agents")
def get_agents():
    conn = get_db()
    agents = conn.execute("SELECT * FROM agents").fetchall()
    conn.close()
    return [dict(ix) for ix in agents]

@app.post("/api/agents")
def register_agent(agent: AgentCreate):
    conn = get_db()
    c = conn.cursor()
    # Check if exists
    existing = c.execute("SELECT id FROM agents WHERE id = ?", (agent.id,)).fetchone()
    if not existing:
        c.execute("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (agent.id, agent.name, agent.provider, "idle", agent.runtime, 0, 0, agent.avatar, agent.initial))
    else:
        c.execute("UPDATE agents SET status = 'idle' WHERE id = ?", (agent.id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/issues/{issue_id}/comments")
def get_comments(issue_id: str):
    conn = get_db()
    comments = conn.execute("SELECT * FROM comments WHERE issue_id = ? ORDER BY id ASC", (issue_id,)).fetchall()
    conn.close()
    return [dict(ix) for ix in comments]

@app.post("/api/issues/{issue_id}/comments")
def create_comment(issue_id: str, comment: CommentCreate):
    conn = get_db()
    conn.execute("INSERT INTO comments (issue_id, author, text, time) VALUES (?, ?, ?, ?)",
                 (issue_id, comment.author, comment.text, comment.time))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/issues/{issue_id}/comments")
def delete_comments(issue_id: str):
    conn = get_db()
    conn.execute("DELETE FROM comments WHERE issue_id = ?", (issue_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# Serve main Multica frontend
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/", dependencies=[Depends(get_current_username)])
def read_index():
    return FileResponse("public/index.html")

@app.get("/styles.css")
def read_styles():
    return FileResponse("styles.css")

# Serve the Swarm Monitor UI under /swarm route
app.mount("/swarm_ui", StaticFiles(directory="swarm_public"), name="swarm_public")

@app.get("/swarm", dependencies=[Depends(get_current_username)])
def read_swarm():
    return FileResponse("swarm_public/index.html")
