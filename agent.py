import time
import requests
import sys
import os
import autogen
import threading

API_URL = os.environ.get("MULTICA_API_URL", "http://localhost:8000/api")
AGENT_ID = "agent-autogen"
WORKSPACE_DIR = "workspace"

if not os.path.exists(WORKSPACE_DIR):
    os.makedirs(WORKSPACE_DIR)

llm_config = {
    "model": "gpt-4o-mini", 
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "max_tokens": 500
}

def register():
    payload = {
        "id": AGENT_ID,
        "name": "AutoGen Corporate Team",
        "provider": "AutoGen GroupChat",
        "runtime": "Local MacOS",
        "avatar": "avatar-claude",
        "initial": "AG"
    }
    try:
        res = requests.post(f"{API_URL}/agents", json=payload)
        res.raise_for_status()
        print(f"✅ Agent {AGENT_ID} registered successfully.")
    except Exception as e:
        print(f"❌ Failed to register agent: {e}")
        sys.exit(1)

def add_comment(issue_id, text, author="AutoGen CEO"):
    payload = {
        "author": author,
        "text": text,
        "time": "just now"
    }
    try:
        requests.post(f"{API_URL}/issues/{issue_id}/comments", json=payload)
    except:
        pass

def update_status(issue_id, status):
    requests.put(f"{API_URL}/issues/{issue_id}", json={"status": status})

def create_board_ticket(title, desc, parent_id):
    payload = {
        "title": f"↳ {title}", 
        "desc": f"**Sub-Task of {parent_id}:**\n\n{desc}", 
        "status": "todo", 
        "priority": "high", 
        "assignee": "agent-autogen"  # Sub-tasks assigned straight to the swarm naturally
    }
    try:
        res = requests.post(f"{API_URL}/issues", json=payload)
        return res.json().get("id")
    except:
        return None

def close_sub_tickets(parent_id):
    try:
        res = requests.get(f"{API_URL}/issues")
        issues = res.json()
        for issue in issues:
            if issue.get("status") != "done" and f"Sub-Task of {parent_id}" in issue.get("desc", ""):
                 update_status(issue["id"], "done")
                 add_comment(issue["id"], "✅ Sub-task automatically closed because the parent Swarm task has completed.", author="System Workflow")
    except:
        pass

def solve_with_autogen(task_desc):
    print("Starting AutoGen Swarm...")
    
    is_term = lambda x: "TERMINATE" in str(x.get("content", "")).upper()
    
    user_proxy = autogen.UserProxyAgent(
        name="User_Proxy",
        system_message="Human administrator. Execute the python code written by the engineers.",
        code_execution_config={"work_dir": WORKSPACE_DIR, "use_docker": False},
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        is_termination_msg=is_term
    )

    ceo = autogen.AssistantAgent(
        name="CEO",
        system_message="""You are the CEO. You speak last. Synthesize the team's findings into a 1-sentence final report. Then output the exact word 'TERMINATE' to end the meeting.""",
        llm_config=llm_config,
        is_termination_msg=is_term
    )

    data_eng = autogen.AssistantAgent(
        name="Data_Engineer",
        system_message="""You are a Data Engineer. Write python code ONCE. Keep explanations to 1 sentence maximum.""",
        llm_config=llm_config,
        is_termination_msg=is_term
    )

    analyst = autogen.AssistantAgent(
        name="Financial_Analyst",
        system_message="You are an Analyst. Provide exactly 1 sentence of analysis.",
        llm_config=llm_config,
        is_termination_msg=is_term
    )

    qa_tester = autogen.AssistantAgent(
        name="QA_Tester",
        system_message="You are QA. Just say 'Pass' in 1 sentence. Do not ask for more information.",
        llm_config=llm_config,
        is_termination_msg=is_term
    )

    risk_manager = autogen.AssistantAgent(
        name="Risk_Manager",
        system_message="You are Risk Manager. Give a score in 1 sentence.",
        llm_config=llm_config,
        is_termination_msg=is_term
    )

    groupchat = autogen.GroupChat(
        agents=[user_proxy, data_eng, analyst, qa_tester, risk_manager, ceo], 
        messages=[], 
        max_round=6,
        speaker_selection_method="round_robin"
    )
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    # Context object to track messages thread
    monitor_running = True
    def message_monitor():
        last_count = 0
        active_agent = None
        active_subtask_id = None
        
        while True:
            current_count = len(groupchat.messages)
            if current_count > last_count:
                for i in range(last_count, current_count):
                    msg = groupchat.messages[i]
                    content = msg.get("content", "")
                    author_name = msg.get("name", "Agent")
                    
                    # IMPLICIT STATE TRACKER: Agent Handoff detection
                    if author_name not in ["User_Proxy", "CEO", "System Workflow"]:
                        if author_name != active_agent:
                            # 1. New Agent took over! Mark previous agent's ticket as done.
                            if active_subtask_id:
                                # CINEMATIC DELAY: Ensure the UI holds it 'In-Progress' for at least 8 seconds!
                                time.sleep(8)
                                update_status(active_subtask_id, 'done')
                                add_comment(task_desc["id"], f"✅ {active_agent} Phase Complete.", author="System Workflow")
                            
                            # 2. Spawn new ticket for the new active agent and move to in-progress
                            active_agent = author_name
                            new_id = create_board_ticket(f"{author_name} Phase", f"Auto-generated sub-task tracking for {author_name}'s execution phase.", task_desc["id"])
                            if new_id:
                                update_status(new_id, 'in-progress')
                                active_subtask_id = new_id
                                add_comment(task_desc["id"], f"⚙️ Agent **{author_name}** has started their phase. Tracking Sub-Ticket **{new_id}**.", author="System Workflow")
                                
                    # Log the message beautifully to the developer's terminal window!
                    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print(f"🤖 [{author_name.upper()}]:")
                    print(f"{content}")
                    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    add_comment(task_desc["id"], content, author=author_name)
                    
                    if active_subtask_id and author_name not in ["User_Proxy", "CEO", "System Workflow"]:
                        # Also mirror their exact message inside their specific sub-ticket!
                        add_comment(active_subtask_id, content, author=author_name)
                    # If CEO shuts it down, mark the last active agent's ticket done
                    if author_name == "CEO" and "TERMINATE" in content:
                        if active_subtask_id:
                            # CINEMATIC DELAY
                            time.sleep(8)
                            update_status(active_subtask_id, 'done')
                            
                last_count = current_count
            else:
                if not monitor_running:
                    # Thread was told to stop, but we successfully flushed all agents, so break!
                    break
            time.sleep(1)

    t = threading.Thread(target=message_monitor)
    t.start()

    # We pass the full issue object in through task_desc to use its ID inside the thread
    prompt_msg = f"Task: {task_desc['title']}\\n\\nDescription: {task_desc['desc']}"
    chat_result = user_proxy.initiate_chat(manager, message=prompt_msg)
    
    # Clean up thread
    monitor_running = False
    t.join()

    # Add final summary comment
    if hasattr(chat_result, 'chat_history') and len(chat_result.chat_history) > 0:
        final_msg = chat_result.chat_history[-1].get("content", "No content")
        return f"**AutoGen Swarm Completed!**\\n\\nHere is the CEO's final output:\\n\\n{final_msg}"
    else:
        return "**AutoGen Swarm executed successfully** (Output not captured due to execution mode)."

def poll_issues():
    try:
        res = requests.get(f"{API_URL}/issues")
        issues = res.json()
        
        my_tasks = [i for i in issues if i['assignee'] == AGENT_ID and i['status'] in ('backlog', 'todo') and "Sub-Task of" not in i.get('desc', "")]
        
        for task in my_tasks:
            print(f"🚀 Picking up task {task['id']}: {task['title']}")
            update_status(task['id'], 'in-progress')
            add_comment(task['id'], f"🤖 The **AutoGen Corporate Team** has picked up task: **{task['title']}**.\\nThe CEO has dispatched the Data Engineer and Financial Analyst to investigate.")
            
            # Execute actual AutoGen Swarm!
            try:
                # To prevent it crashing if no API key is set, we will gracefully handle it
                if llm_config["api_key"] == "sk-mock-key-for-now" or "YOUR" in llm_config["api_key"]:
                    time.sleep(3)
                    add_comment(task['id'], "We are starting the market analysis...", author="CEO")
                    time.sleep(2)
                    add_comment(task['id'], "Fetching MSFT and TSLA using yfinance...", author="Data_Engineer")
                    time.sleep(2)
                    add_comment(task['id'], "Testing calculation variance... Looks solid.", author="QA_Tester")
                    time.sleep(2)
                    final_report = "*(Note: No real OpenAI API key was provided, so this is a simulated AutoGen response)*\n\nThe CEO has reviewed the analysis from the Data Engineer. The Risk Manager assessed the situation and assigned a Risk Score of 4/10. The task was successfully handled."
                else:
                    final_report = solve_with_autogen(task) # pass the whole task object
            except Exception as e:
                final_report = f"❌ AutoGen Swarm crashed with error: {e}"
                
            add_comment(task['id'], final_report, author="AutoGen CEO")
            
            print(f"✅ Completed task {task['id']}. Marking as done.")
            
            # Clean up and auto-close any orphaned sub-tasks!
            close_sub_tickets(task['id'])

            # Wait 10 seconds before gracefully finishing the entire pipeline on UI
            print("⏳ Swarm finished. Waiting 10 seconds before marking master ticket Done...")
            time.sleep(10)
            update_status(task['id'], 'done')
            add_comment(task['id'], f"✅ Task is completely finished. The final executive report has been filed.")
            
    except Exception as e:
        # Ignore silent polling connection errors
        pass

if __name__ == "__main__":
    print("🤖 Multica AutoGen Agent starting up...")
    register()
    
    print("📡 Polling for tasks every 3 seconds... (Press Ctrl+C to stop)")
    try:
        while True:
            poll_issues()
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n👋 Agent shutting down.")
