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
import logging

# Suppress AutoGen's outdated API key format warnings
logging.getLogger("autogen.oai.client").setLevel(logging.ERROR)

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

def agent_create_sub_ticket(title, desc, parent_id):
    try:
        res = http_requests.post(f"{API_BASE}/issues", json={
            "title": f"↳ {title}", 
            "desc": f"**Sub-Task of {parent_id}:**\n\n{desc}", 
            "status": "todo", 
            "priority": "high", 
            "assignee": "agent-autogen"
        }, timeout=5)
        return res.json().get("id")
    except: return None

def agent_close_orphaned_sub_tickets(parent_id):
    try:
        res = http_requests.get(f"{API_BASE}/issues", timeout=5)
        issues = res.json()
        for issue in issues:
            if issue.get("status") != "done" and f"Sub-Task of {parent_id}" in issue.get("desc", ""):
                 agent_update_status(issue["id"], "done")
                 agent_add_comment(issue["id"], "✅ Sub-task automatically closed because the parent Swarm task has completed.", author="System Workflow")
    except: pass

def agent_solve_task(task):
    """Run AutoGen swarm for a task with original feature set."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Simulation mode — no OpenAI key
        agent_add_comment(task["id"], "🤖 The **AutoGen Corporate Team** has picked up task: **simulation mode**.\\nThe CEO has dispatched the team to investigate.", author="System Workflow")
        time.sleep(3)
        agent_add_comment(task["id"], "We are starting the market analysis...", author="CEO")
        time.sleep(2)
        agent_add_comment(task["id"], "Fetching relevant market data using simulated tools...", author="Data_Engineer")
        time.sleep(2)
        agent_add_comment(task["id"], "Testing calculation variance... Looks solid.", author="QA_Tester")
        time.sleep(2)
        agent_add_comment(task["id"], "*(Simulated Response)*\nThe CEO has reviewed the analysis. The Risk Manager assessed the situation and assigned a Risk Score of 4/10. The task was successfully handled.", author="AutoGen CEO")
        return

    try:
        import autogen
        llm_config = {"model": "gpt-4o-mini", "api_key": api_key, "max_tokens": 500}
        is_term = lambda x: "TERMINATE" in str(x.get("content", "")).upper()

        user_proxy = autogen.UserProxyAgent(
            name="User_Proxy",
            system_message="Human administrator. Execute the python code written by the engineers.",
            code_execution_config={"work_dir": "workspace", "use_docker": False},
            human_input_mode="NEVER", max_consecutive_auto_reply=10, is_termination_msg=is_term
        )
        
        agents_list = [
            autogen.AssistantAgent("Data_Engineer", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are a Data Engineer. Write python code ONCE. Keep explanations to 1 sentence maximum."),
            autogen.AssistantAgent("Financial_Analyst", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are an Analyst. Provide exactly 1 sentence of analysis."),
            autogen.AssistantAgent("QA_Tester", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are QA. Just say 'Pass' in 1 sentence. Do not ask for more information."),
            autogen.AssistantAgent("Risk_Manager", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are Risk Manager. Give a score in 1 sentence."),
            autogen.AssistantAgent("CEO", llm_config=llm_config, is_termination_msg=is_term,
                system_message="You are the CEO. You speak last. Synthesize the team's findings into a 1-sentence final report. Then output the exact word 'TERMINATE' to end the meeting."),
        ]
        
        groupchat = autogen.GroupChat(
            agents=[user_proxy] + agents_list, messages=[], max_round=8,
            speaker_selection_method="round_robin"
        )
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

        # STATE TRACKER
        monitor_state = {"active_agent": None, "active_subtask_id": None, "running": True}

        def message_monitor():
            last_count = 0
            while monitor_state["running"]:
                current_count = len(groupchat.messages)
                if current_count > last_count:
                    for i in range(last_count, current_count):
                        msg = groupchat.messages[i]
                        content = msg.get("content", "")
                        author_name = msg.get("name", "Agent")
                        
                        # IMPLICIT STATE TRACKER: Agent Handoff detection
                        if author_name not in ["User_Proxy", "CEO", "System Workflow"]:
                            if author_name != monitor_state["active_agent"]:
                                # 1. Mark previous agent phase as done with 8s delay
                                if monitor_state["active_subtask_id"]:
                                    time.sleep(8)
                                    agent_update_status(monitor_state["active_subtask_id"], 'done')
                                    agent_add_comment(task["id"], f"✅ {monitor_state['active_agent']} Phase Complete.", author="System Workflow")
                                
                                # 2. New Sub-ticket
                                monitor_state["active_agent"] = author_name
                                new_id = agent_create_sub_ticket(f"{author_name} Phase", f"Auto-generated sub-task tracking for {author_name}'s execution phase.", task["id"])
                                if new_id:
                                    agent_update_status(new_id, 'in-progress')
                                    monitor_state["active_subtask_id"] = new_id
                                    agent_add_comment(task["id"], f"⚙️ Agent **{author_name}** has started their phase. Tracking Sub-Ticket **{new_id}**.", author="System Workflow")
                                    
                        agent_add_comment(task["id"], content, author=author_name)
                        if monitor_state["active_subtask_id"] and author_name not in ["User_Proxy", "CEO", "System Workflow"]:
                            agent_add_comment(monitor_state["active_subtask_id"], content, author=author_name)

                    last_count = current_count
                time.sleep(1)

        mon_thread = threading.Thread(target=message_monitor, daemon=True)
        mon_thread.start()

        prompt_msg = f"Task: {task['title']}\\n\\nDescription: {task['desc']}"
        chat_result = user_proxy.initiate_chat(manager, message=prompt_msg)
        
        monitor_state["running"] = False
        mon_thread.join(timeout=5)
        
        if hasattr(chat_result, 'chat_history') and len(chat_result.chat_history) > 0:
            final_msg = chat_result.chat_history[-1].get("content", "No content")
            return f"**AutoGen Swarm Completed!**\\n\\nHere is the CEO's final output:\\n\\n{final_msg}"
        return "✅ AutoGen Swarm executed successfully."

    except Exception as e:
        return f"❌ AutoGen Swarm crashed with error: {e}"

def agent_polling_loop():
    print("🤖 Multica AutoGen Agent starting up...", flush=True)
    time.sleep(5)
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
                print(f"🚀 Picking up task {task['id']}: {task['title']}", flush=True)
                agent_update_status(task['id'], 'in-progress')
                agent_add_comment(task['id'], f"🤖 The **AutoGen Corporate Team** has picked up task: **{task['title']}**.\\nThe CEO has dispatched the team to investigate.", author="System Workflow")
                
                # Execute Swarm
                final_report = agent_solve_task(task)
                agent_add_comment(task['id'], final_report, author="AutoGen CEO")
                
                # Cleanup and 10s delay before closing master ticket
                agent_close_orphaned_sub_tickets(task['id'])
                print(f"⏳ Swarm finished. Waiting 10 seconds before marking master ticket Done...", flush=True)
                time.sleep(10)
                agent_update_status(task['id'], 'done')
                agent_add_comment(task['id'], f"✅ Task is completely finished. The final executive report has been filed.", author="System Workflow")
                print(f"✅ Completed task {task['id']}", flush=True)
        except Exception as e:
            pass
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
