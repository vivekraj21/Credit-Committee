import gradio as gr
import requests
import json
import uuid
import time
import sys
import os

# Ensure project root is in sys.path to allow absolute imports from 'src'
# The root is the parent of the 'src' directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Styling for a premium boardroom feel
BOARDROOM_CSS = """
.boardroom-container { background-color: #0f172a; color: white; border-radius: 12px; padding: 20px; }
.agent-card { background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
.agent-card.active { border-color: #38bdf8; box-shadow: 0 0 10px rgba(56, 189, 248, 0.3); }
.status-joined { color: #10b981; font-weight: bold; }
.status-analyzing { color: #f59e0b; font-weight: bold; }
.conflict-badge { background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
.consensus-bar { height: 10px; background: #1e293b; border-radius: 5px; overflow: hidden; }
.consensus-progress { height: 100%; background: #38bdf8; width: 0%; transition: width 0.5s ease; }
"""

def run_committee_demo(company_name, industry, revenue, amount, debt_ratio, credit_score):
    app_id = str(uuid.uuid4())[:8]
    payload = {
        "id": app_id,
        "company_name": company_name,
        "industry": industry,
        "country": "USA",
        "revenue": float(revenue),
        "requested_amount": float(amount),
        "debt_ratio": float(debt_ratio),
        "credit_score": int(credit_score)
    }
    
    # Internal simulation for demo (since we're running it UI-side for speed)
    from src.graph.graph import create_committee_graph
    from src.collaboration.band_wrapper import band
    
    graph = create_committee_graph()
    initial_state = {
        "application_data": payload,
        "room_id": "",
        "agent_registry": [],
        "recruited_agents": [],
        "agent_findings": {},
        "agent_messages": [],
        "debate_history": [],
        "conflicts": [],
        "consensus_summary": {},
        "final_decision": {},
        "confidence_score": 0.0,
        "committee_events": [],
        "policy_references": [],
        "current_phase": "Intake",
        "is_consensus_reached": False,
        "needs_dynamic_recruitment": False
    }
    
    # We yield updates for visual effect
    yield "Room Creating...", [], "Waiting for Agents...", "Initial Analysis", "N/A", "Processing..."
    
    try:
        # Step by step execution for UI feedback
        result = graph.invoke(initial_state)
        
        room_id = result["room_id"]
        messages = band.get_room_history(room_id)
        msg_html = "".join([f"<div style='margin-bottom: 8px; border-bottom: 1px solid #334155; padding-bottom: 4px;'><b>{m['sender']}:</b> {m['text']}</div>" for m in messages])
        
        findings = result["agent_findings"]
        findings_html = "".join([f"<div class='agent-card'><b>{k}</b><br><span style='color: #38bdf8;'>{v.get('recommendation')}</span>: {v.get('findings')[:150]}...</div>" for k, v in findings.items()])
        
        conflicts = result["conflicts"]
        conflict_html = "None" if not conflicts else f"<span class='conflict-badge'>Conflict: {conflicts[0]['type']}</span>"
        
        outcome = result["final_decision"]
        
        yield (
            f"Room: {room_id}",
            msg_html,
            findings_html,
            outcome.get("final_outcome"),
            conflict_html,
            outcome.get("executive_summary")
        )
    except Exception as e:
        error_msg = f"⚠️ **Board Meeting Interrupted**\n\nERROR: {str(e)}\n\n*Check your .env file and API keys.*"
        yield (
            "Room: ERROR",
            "Meeting halted due to error.",
            "Agents disconnected.",
            "ERROR",
            "N/A",
            error_msg
        )

with gr.Blocks() as demo:
    gr.Markdown("# 🏢 AI Corporate Credit Committee")
    gr.Markdown("### Digital Boardroom Dashboard - Powered by Band & LangGraph")
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📜 Loan Application")
            company = gr.Textbox(label="Company Name", value="Global Tech Corp")
            industry = gr.Textbox(label="Industry", value="Technology")
            revenue = gr.Number(label="Annual Revenue ($M)", value=500)
            amount = gr.Number(label="Requested Amount ($M)", value=50)
            debt_ratio = gr.Slider(0, 100, label="Debt-to-Income Ratio (%)", value=25)
            credit_score = gr.Number(label="Credit Score", value=780)
            btn = gr.Button("🚀 Convene Board", variant="primary")
            
        with gr.Column(scale=2):
            with gr.Row():
                room_status = gr.Markdown("### 🏠 Band Room Status\nWaiting to start...")
                conflict_status = gr.HTML("<div style='text-align: right;'>Conflict Level: N/A</div>")
            
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 👥 Agent Council")
                    agent_council = gr.HTML("<div class='agent-card'>Agents will appear here...</div>")
                
                with gr.Column(scale=2):
                    gr.Markdown("### 💬 Live Collaboration Feed (Band)")
                    live_feed = gr.HTML("<div style='height: 300px; overflow-y: scroll; background: #1e293b; padding: 10px; border-radius: 8px;'></div>")

        with gr.Column(scale=1):
            gr.Markdown("### ⚖️ Board Resolution")
            decision = gr.Label(label="Final Decision")
            executive_summary = gr.Textbox(label="Executive Summary", lines=10)

    btn.click(
        run_committee_demo,
        inputs=[company, industry, revenue, amount, debt_ratio, credit_score],
        outputs=[room_status, live_feed, agent_council, decision, conflict_status, executive_summary]
    )

if __name__ == "__main__":
    demo.launch(server_port=7860, css=BOARDROOM_CSS, theme=gr.themes.Soft(primary_hue="blue"))
