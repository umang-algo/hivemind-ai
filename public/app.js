'use strict';

const state = {
  currentView: 'issues',
  viewMode: 'board', // 'board' | 'list'
  selectedIssue: null,
  dragCard: null,
  dragFromColumn: null,

  issues: [],
  agents: [],

  runtimes: [
    { id: 'rt-1', name: 'My MacBook Pro', host: 'localhost', clis: ['python-agent'], status: 'active', os: '🍎' },
    { id: 'rt-2', name: 'Cloud Runner #1', host: 'cloud-1.multica.ai', clis: ['openclaw'], status: 'active', os: '☁️' }
  ],
  skills: [],
  inbox: []
};

const COLUMNS = [
  { id: 'backlog',     label: 'Backlog',     dotClass: 'backlog',     color: '#a1a1aa' },
  { id: 'todo',        label: 'Todo',        dotClass: 'todo',        color: '#e4e4e7' },
  { id: 'in-progress', label: 'In Progress', dotClass: 'in-progress', color: '#f59e0b' },
  { id: 'in-review',   label: 'In Review',   dotClass: 'in-review',   color: '#22c55e' },
  { id: 'done',        label: 'Done',        dotClass: 'done',        color: '#3b82f6' },
];

const PRIORITY_LABELS = { urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low' };

function getAssigneeLabel(id) {
  if (id === 'human') return 'Umang Yadav';
  const ag = state.agents.find(a => a.id === id);
  return ag ? ag.name : id;
}

function getAssigneeAvatar(id) {
  if (id === 'human') return { cls: 'avatar-human', init: 'U' };
  const ag = state.agents.find(a => a.id === id);
  return ag ? { cls: ag.avatar || 'avatar-claude', init: ag.initial || 'A' } : { cls: 'avatar-claude', init: '?' };
}

async function fetchData() {
  try {
    const resIssues = await fetch('/api/issues');
    state.issues = await resIssues.json();

    const resAgents = await fetch('/api/agents');
    state.agents = await resAgents.json();
    
    // Update UI based on fetched data
    updateAssigneeDropdown();
    refreshCurrentView();
  } catch (err) {
    console.error("Failed to fetch data:", err);
    showToast("Error connecting to server", 3000);
  }
}

function updateAssigneeDropdown() {
  const select = document.getElementById('issueAssignee');
  if (!select) return;
  const currentValue = select.value;

  // Always start with human + hardcoded AutoGen fallback
  const fallbackAgents = [
    { id: 'agent-autogen', name: '🤖 AutoGen Swarm' },
  ];

  select.innerHTML = `<option value="human">👤 Umang Yadav</option>`;

  // Merge live API agents with fallbacks (avoid duplicates)
  const liveIds = state.agents.map(a => a.id);
  const merged = [
    ...state.agents,
    ...fallbackAgents.filter(f => !liveIds.includes(f.id))
  ];

  merged.forEach(ag => {
    select.innerHTML += `<option value="${ag.id}">${ag.name}</option>`;
  });

  if (currentValue) select.value = currentValue;
}

function refreshCurrentView() {
  if (state.currentView === 'issues') {
    state.viewMode === 'board' ? renderBoard() : renderList();
  } else if (state.currentView === 'agents') renderAgents();
  else if (state.currentView === 'my-issues') renderMyIssues();
}

function switchView(viewName) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const navEl = document.getElementById(`nav-${viewName}`);
  if (navEl) navEl.classList.add('active');

  document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
  const targetView = document.getElementById(`view-${viewName}`);
  if (targetView) targetView.classList.remove('hidden');

  state.currentView = viewName;

  if (viewName === 'issues') state.viewMode === 'board' ? renderBoard() : renderList();
  else if (viewName === 'agents') renderAgents();
  else if (viewName === 'runtimes') renderRuntimes();
  else if (viewName === 'skills') renderSkills();
  else if (viewName === 'inbox') renderInbox();
  else if (viewName === 'my-issues') renderMyIssues();
  else if (viewName === 'settings') renderSettings();
}

// ════ BOARD ════
function renderBoard() {
  const container = document.getElementById('boardContainer');
  container.innerHTML = '';
  COLUMNS.forEach(col => {
    const issues = state.issues.filter(i => i.status === col.id);
    container.appendChild(createColumnEl(col, issues));
  });
  updateIssuesCount();
}

function createColumnEl(col, issues) {
  const div = document.createElement('div');
  div.className = 'kanban-column';
  div.dataset.status = col.id;

  div.innerHTML = `
    <div class="column-header">
      <div class="column-status-dot ${col.dotClass}"></div>
      <span class="column-title">${col.label}</span>
      <span class="column-count">${issues.length}</span>
      <button class="column-add-btn" data-status="${col.id}" title="Add issue">
        <svg viewBox="0 0 12 12" fill="none""><path d="M6 1V11M1 6H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    </div>
    <div class="column-cards" id="cards-${col.id}"></div>
  `;

  div.addEventListener('dragover', e => { e.preventDefault(); div.classList.add('drag-over'); });
  div.addEventListener('dragleave', e => { if (!div.contains(e.relatedTarget)) div.classList.remove('drag-over'); });
  div.addEventListener('drop', async e => {
    e.preventDefault();
    div.classList.remove('drag-over');
    if (state.dragCard) {
      const issue = state.issues.find(i => i.id === state.dragCard);
      if (issue && issue.status !== col.id) {
        issue.status = col.id;
        renderBoard(); // optimistic UI
        await fetch(`/api/issues/${issue.id}`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({status: col.id})
        });
        showToast(`Moved ${issue.id} to ${col.label}`);
      }
    }
  });

  const cardsContainer = div.querySelector(`#cards-${col.id}`);
  issues.forEach(issue => cardsContainer.appendChild(createIssueCardEl(issue)));

  div.querySelector('.column-add-btn').addEventListener('click', () => openNewIssueModal(col.id));
  return div;
}

function createIssueCardEl(issue) {
  const card = document.createElement('div');
  card.className = 'issue-card';
  card.dataset.id = issue.id;
  card.draggable = true;

  const av = getAssigneeAvatar(issue.assignee);
  const isAgent = issue.assignee !== 'human';

  const isSubtask = issue.desc ? issue.desc.match(/Sub-Task of (MUL-\d+)/) : null;
  const subtaskBadge = isSubtask ? `<div style="font-size:10px; background:#312e81; color:#c7d2fe; border:1px solid #4338ca; padding:2px 6px; border-radius:4px; display:inline-block; margin-bottom:6px; font-weight:600;">↪ Part of ${isSubtask[1]}</div>` : '';

  card.innerHTML = `
    <div class="issue-card-top"><span class="issue-id">${issue.id}</span></div>
    ${subtaskBadge}
    <div class="issue-title">${escapeHtml(issue.title)}</div>
    <div class="issue-card-footer">
      <span class="priority-badge ${issue.priority}">${PRIORITY_LABELS[issue.priority]}</span>
      <div class="issue-footer-right">
        ${isAgent ? `<span class="agent-tag">AI</span>` : ''}
        <div class="assignee-avatar ${av.cls}" title="${getAssigneeLabel(issue.assignee)}">${av.init}</div>
      </div>
    </div>
  `;

  card.addEventListener('dragstart', e => {
    state.dragCard = issue.id;
    card.classList.add('dragging');
  });
  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
    state.dragCard = null;
  });
  card.addEventListener('click', () => openIssueDetail(issue.id));

  return card;
}

// ════ API ACTIONS ════
async function updateIssueStatus(id, newStatus) {
  const issue = state.issues.find(i => i.id === id);
  if (issue) {
    issue.status = newStatus;
    renderBoard();
    await fetch(`/api/issues/${id}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: newStatus})
    });
    showToast(`Status updated`);
  }
}

async function saveNewIssue() {
  const title = document.getElementById('issueTitle').value.trim();
  if (!title) return;

  const newIssue = {
    title,
    desc: document.getElementById('issueDesc').value.trim(),
    status: document.getElementById('issueStatus').value,
    priority: document.getElementById('issuePriority').value,
    assignee: document.getElementById('issueAssignee').value,
  };

  closeNewIssueModal();
  
  const res = await fetch('/api/issues', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(newIssue)
  });
  const data = await res.json();
  
  newIssue.id = data.id;
  newIssue.created = "just now";
  state.issues.unshift(newIssue);
  
  state.viewMode === 'board' ? renderBoard() : renderList();
  showToast(`${newIssue.id} created`);

  if (newIssue.assignee === 'agent-autogen') {
    const swarmUrl = `${window.location.origin}/swarm?issueId=${newIssue.id}`;
    window.open(swarmUrl, '_blank');
  }
}

// ════ RENDERERS ════
function renderRuntimes() {
  const list = document.getElementById('runtimesList');
  list.innerHTML = `
    <div style="background:#f0eeff;border:1px solid #c4b5fd;border-radius:10px;padding:14px 16px;margin-bottom:14px;">
      <p style="font-size:12.5px;font-weight:600;color:#4f46e5;margin-bottom:4px;">🔌 Connect your machine</p>
      <p style="font-size:12px;color:#6b6b7a;">Run <code style="background:#ede9fe;padding:1px 5px;border-radius:4px;">python3 agent.py</code> to start your daemon.</p>
    </div>
  `;
  state.runtimes.forEach(rt => {
    list.innerHTML += `
      <div class="runtime-card">
        <div class="runtime-icon">${rt.os}</div>
        <div class="runtime-info">
          <div class="runtime-name">${rt.name}</div><div class="runtime-host">${rt.host}</div>
          <div class="runtime-clis">${rt.clis.map(c => `<span class="cli-tag">${c}</span>`).join('')}</div>
        </div>
        <div class="runtime-card-meta">
          <div class="agent-status-badge ${rt.status}">${rt.status}</div>
        </div>
      </div>
    `;
  });
}

function renderAgents() {
  const grid = document.getElementById('agentsGrid');
  grid.innerHTML = '';
  state.agents.forEach(agent => {
    grid.innerHTML += `
      <div class="agent-card">
        <div class="agent-card-header">
          <div class="agent-avatar-lg ${agent.avatar || 'avatar-claude'}">${agent.initial || 'A'}</div>
          <div class="agent-card-info">
            <div class="agent-card-name">${agent.name}</div>
            <div class="agent-card-provider">${agent.provider} · ${agent.runtime}</div>
          </div>
          <div class="agent-status-badge ${agent.status}">${agent.status}</div>
        </div>
      </div>
    `;
  });
}

// Rest of views simplified for brevity...
function renderList() {} function renderSkills() {} function renderInbox() {} function renderMyIssues() {} function renderSettings() {}

async function openIssueDetail(issueId) {
  const issue = state.issues.find(i => i.id === issueId);
  if (!issue) return;
  state.selectedIssue = issueId;
  const panel = document.getElementById('issueDetailPanel');
  const body = document.getElementById('detailBody');
  const col = COLUMNS.find(c => c.id === issue.status);
  
  body.innerHTML = `
    <div class="detail-issue-id">${issue.id}</div>
    <h2 class="detail-title">${escapeHtml(issue.title)}</h2>
    <div class="detail-status-row"><span class="priority-badge ${issue.priority}">${PRIORITY_LABELS[issue.priority]}</span></div>
    <p class="detail-desc">${escapeHtml(issue.desc)}</p>
    <div style="display:flex;gap:8px;margin-top:16px;margin-bottom:20px;">
      <select style="flex:1;padding:7px;border-radius:8px;" onchange="updateIssueStatus('${issue.id}', this.value)">
        ${COLUMNS.map(c => `<option value="${c.id}" ${c.id === issue.status ? 'selected' : ''}>${c.label}</option>`).join('')}
      </select>
    </div>
    <div class="detail-comments-title">Activity</div>
    <div id="commentsContainer" style="font-size:12px;color:#6b6b7a;">Loading...</div>
  `;
  panel.classList.remove('hidden');

  try {
    const res = await fetch(`/api/issues/${issueId}/comments`);
    const comments = await res.json();
    const container = document.getElementById('commentsContainer');
    container.innerHTML = '';
    if (comments.length === 0) {
      container.innerHTML = 'No activity yet.';
    } else {
      comments.forEach(c => {
        let textCodeFmt = escapeHtml(c.text).replace(/```([\s\S]*?)```/g, '<pre style="background:#f4f4f5;padding:8px;border-radius:6px;overflow-x:auto;margin-top:6px;font-family:monospace;border:1px solid #e4e4e7"><code>$1</code></pre>');
        container.innerHTML += `
        <div class="detail-comment">
          <div class="comment-avatar avatar-claude" style="background:#4f46e5;color:#fff">${c.author[0]}</div>
          <div class="comment-body">
            <div class="comment-header">
              <span class="comment-author">${escapeHtml(c.author)}</span>
              <span class="comment-time">${escapeHtml(c.time)}</span>
            </div>
            <div class="comment-text" style="white-space: pre-wrap;">${textCodeFmt}</div>
          </div>
        </div>
        `;
      });
    }
  } catch(e) {}
}

function openNewIssueModal(defaultStatus = 'backlog') {
  document.getElementById('issueStatus').value = defaultStatus;
  document.getElementById('issueTitle').value = '';
  document.getElementById('newIssueModal').classList.remove('hidden');
  setTimeout(() => document.getElementById('issueTitle').focus(), 100);
}
function closeNewIssueModal() { document.getElementById('newIssueModal').classList.add('hidden'); }
function updateIssuesCount() { const el = document.getElementById('issuesCount'); if(el) el.textContent = `${state.issues.length} Issues`; }
function showToast(msg, dur=2500) { const el = document.getElementById('toast'); document.getElementById('toastMsg').textContent=msg; el.classList.remove('hidden'); setTimeout(()=>el.classList.add('hidden'),dur); }
function escapeHtml(s) { return String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

window.updateIssueStatus = updateIssueStatus;

// ════ INIT ════
document.addEventListener('DOMContentLoaded', () => {
  ['inbox', 'my-issues', 'issues', 'agents', 'runtimes', 'skills', 'settings'].forEach(view => {
    document.getElementById(`link-${view}`)?.addEventListener('click', e => { e.preventDefault(); switchView(view); });
  });

  document.getElementById('newIssueBtn')?.addEventListener('click', () => openNewIssueModal());
  document.getElementById('saveIssueBtn')?.addEventListener('click', saveNewIssue);
  document.getElementById('cancelIssueBtn')?.addEventListener('click', closeNewIssueModal);
  document.getElementById('closeIssueModal')?.addEventListener('click', closeNewIssueModal);
  document.getElementById('closeDetailPanel')?.addEventListener('click', () => document.getElementById('issueDetailPanel').classList.add('hidden'));

  // Start data polling every 5 seconds to get updates from agents automatically
  fetchData();
  setInterval(fetchData, 3000);
});
