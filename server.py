import sqlite3
import json
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

app = FastAPI(title="Multica Backend")

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
        ]
        c.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_agents)
        
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
