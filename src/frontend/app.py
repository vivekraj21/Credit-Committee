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

# V7 Ultra-Compact Professional Boardroom
from src.graph.graph import create_committee_graph
from src.collaboration.band_wrapper import band

print(f"--- 🔑 RUNTIME KEY CHECK ---")
print(f"GROQ_KEY: {str(os.getenv('GROQ_API_KEY'))[:8]}...")
print(f"TAVILY_KEY: {str(os.getenv('TAVILY_API_KEY'))[:8]}...")
print(f"----------------------------")

BOARDROOM_CSS = """
body { background-color: #f3f2ef; font-family: -apple-system, sans-serif; margin: 0; padding: 0; }
.gradio-container { background-color: #f3f2ef !important; }
.boardroom-container { background: white; border-radius: 8px; border: 1px solid #e0dfdc; padding: 10px; margin-top: 0 !important; max-height: 600px; }

/* Ultra-Compact Chat Feed */
#chat-feed { 
    height: 400px; 
    overflow-y: auto; 
    padding: 10px; 
    display: flex; 
    flex-direction: column; 
    gap: 8px; scroll-behavior: smooth; 
    background: #ffffff;
    border: 1px solid #e0dfdc;
    border-radius: 4px;
}

.chat-msg { display: flex; flex-direction: column; max-width: 95%; }
.msg-header { display: flex; align-items: center; gap: 4px; margin-bottom: 2px; font-size: 0.7rem; color: #666; }
.agent-status { font-weight: 600; background: #e7f3ff; padding: 0px 6px; border-radius: 10px; color: #0077b5; font-size: 0.6rem; }

.chat-bubble { padding: 8px 12px; border-radius: 0 8px 8px 8px; font-size: 13px; line-height: 1.4; border: 1px solid #e0dfdc; }
.bubble-agent { background: #f9fafb; color: #333; align-self: flex-start; }
.bubble-chairman { background: #0077b5; color: white; border-color: #0077b5; align-self: flex-start; }
.bubble-system { align-self: center; background: transparent; color: #666; font-size: 11px; padding: 5px; border-top: 1px solid #e0dfdc; width: 100%; text-align: center; }

h1, h2, h3, p, span, label { color: #333 !important; margin: 0 !important; }
.active-speaker { border-left: 3px solid #0077b5; background: rgba(0, 119, 181, 0.03); }

/* Compact Inputs */
input, textarea { background: #f9fafb !important; border: 1px solid #e0dfdc !important; padding: 4px !important; }
.label-style { font-size: 0.8rem !important; }
"""

# JavaScript for auto-scrolling
AUTO_SCROLL_JS = """
function scroll_to_bottom() {
    var element = document.getElementById('chat-feed');
    if (element) { element.scrollTop = element.scrollHeight; }
}
"""

def format_message_v3(m, findings, current_phase):
    sender = m['sender']
    text = m['text']
    status = findings.get(sender, {}).get("recommendation", "PARTICIPATING")
    
    cls = "bubble-agent"
    header_html = f"<div class='msg-header'><span>{sender}</span><span class='agent-status'>{status}</span></div>"
    
    if sender == "System": 
        cls = "bubble-system"
        header_html = ""
    elif sender == "Committee Chairman": 
        cls = "bubble-chairman"
    
    active_cls = "active-speaker" if sender in current_phase or (current_phase == "Board Debate" and sender != "System") else ""
    
    return f"""
    <div class="chat-msg {active_cls}">
        {header_html}
        <div class="chat-bubble {cls}">{text}</div>
    </div>
    """

def parse_uploaded_files(files):
    extracted_data = []
    if not files: return extracted_data
    
    import pypdf
    for f in files:
        fname = os.path.basename(f.name)
        text = ""
        if fname.endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(f.name)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            except: text = f"Error reading PDF: {fname}"
        else:
            with open(f.name, "r", encoding="utf-8", errors="ignore") as tf:
                text = tf.read()
        extracted_data.append({"name": fname, "content": text})
    return extracted_data

def format_mermaid_map(messages):
    """Generates Mermaid visualizer code from room history."""
    # Simple flow diagram showing mentions
    nodes = set(["Chairman", "Analyst", "Risk", "Compliance", "Research"])
    edges = []
    for m in messages:
        sender = m['sender'].replace(" ", "")
        text = m['text']
        if "@ResearchSpecialist" in text:
            edges.append(f"{sender}-->|Request|Research")
        if "provided the requested data" in text.lower():
            edges.append(f"Research-->|Evidence|{sender}")
        if "@" in text and sender != "System":
            # Extract other mentions
            for n in nodes:
                if f"@{n}" in text:
                    edges.append(f"{sender}-->|Rebuttal|{n}")
    
    # Unique edges
    edges = list(set(edges))
    mermaid_code = "graph TD\n" + "\n".join(edges if edges else ["Chairman-->Analyst", "Chairman-->Risk", "Chairman-->Compliance"])
    
    return f"""
    <div class="mermaid">
    {mermaid_code}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true }});
    </script>
    """

def run_committee_demo(company_name, amount):
    import uuid
    app_id = str(uuid.uuid4())[:8]
    
    payload = {
        "id": app_id,
        "company_name": company_name,
        "requested_amount": float(amount),
        "research_mode": "Auto",
        "manual_evidence": [],
        "industry": "Researching...",
        "revenue": 0.0,
        "debt_ratio": 0,
        "credit_score": 0
    }
    
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
        "current_phase": "Intake (Auto)",
        "is_consensus_reached": False,
        "needs_dynamic_recruitment": False
    }
    
    yield "...", "", "WAITING", "...", gr.update(), "", "<div>Init...</div>", "<div>Checking...</div>"
    
    try:
        current_state = initial_state
        # Limit rounds for control
        for i, output in enumerate(graph.stream(current_state)):
            node_name = list(output.keys())[0]
            current_state.update(output[node_name])
            
            room_id = current_state.get("room_id", "N/A")
            phase = current_state.get("current_phase", "Debate")
            
            messages = band.get_room_history(room_id)
            msg_html = f"<div id='chat-feed'>{''.join([format_message_v3(m, {}, phase) for m in messages])}</div>"
            
            # Dynamic Checklist Logic
            categories = ["FINANCIALS", "NEWS", "COMPLIANCE"]
            fulfilled = []
            for m in messages:
                m_meta = m.get("metadata", {})
                if "file" in m_meta:
                    fulfilled.append(m_meta["file"].get("category", "GENERAL").upper())

            checklist_html = "<div class='checklist'>"
            for cat in categories:
                status = "✅" if cat in fulfilled else "❌"
                color = "green" if cat in fulfilled else "red"
                checklist_html += f"<div style='color: {color}'>{status} {cat}</div>"
            checklist_html += "</div>"

            files = [m["metadata"]["file"]["name"] for m in messages if "file" in m.get("metadata", {})]
            
            outcome = current_state.get("final_decision", {})
            decision_text = outcome.get("final_outcome", "PENDING")
            summary = outcome.get("executive_summary", "Board deliberating...")
            
            yield (
                phase, msg_html, decision_text, summary,
                gr.update(choices=files, value=files[-1] if files else None),
                room_id, format_mermaid_map(messages), checklist_html
            )
            time.sleep(0.5)

    except Exception as e:
        print(f"[CRITICAL_ERROR] {str(e)}")
        yield ("Error", f"<div class='bubble-system'>Error: {str(e)}</div>", "ERROR", "Halted.", gr.update(), "", "<div>Error</div>", "<div>Halted</div>")

with gr.Blocks() as demo:
    with gr.Row():
        gr.HTML("""
            <div style='text-align: center; padding: 5px;'>
                <h2 style='color: #0077b5; margin: 0;'>🏢 AI Credit Committee</h2>
                <p style='color: #666; font-size: 0.8rem; margin: 0;'>Autonomous Data-Driven Boardroom</p>
            </div>
        """)

    with gr.Row(elem_classes="boardroom-container"):
        with gr.Column(scale=1):
            gr.Markdown("#### 📋 Intake")
            with gr.Group():
                company = gr.Textbox(label="Company Name", placeholder="e.g. Acme Corp", value="Veridian Dynamics")
                amount = gr.Number(label="Loan Amount ($M)", value=150)
                btn = gr.Button("🚀 Start Committee", variant="primary")
            
            # --- Status Check ---
            gr.Markdown("#### 📋 Search Status")
            evidence_checklist = gr.HTML("<div class='checklist'>Ready for autonomous research.</div>")

        with gr.Column(scale=3):
            room_status = gr.Markdown("#### 🏠 Live Boardroom Feed")
            live_feed = gr.HTML("<div id='chat-feed'><div class='bubble-system'>Enter request details to begin.</div></div>")
            
            with gr.Accordion("📊 Collaboration Visualizer", open=False):
                collaboration_map = gr.HTML("<div id='mermaid-container'>Loading...</div>")

        with gr.Column(scale=1):
            gr.Markdown("#### ⚖️ Resolution")
            decision = gr.Label(label="Board Vote", value="WAITING")
            executive_summary = gr.Markdown("#### Summary\n*Evidence-based analysis pending.*")
            
            gr.Markdown("---")
            gr.Markdown("#### 📂 Evidence")
            evidence_files = gr.Dropdown(label="Research Docs", choices=[], interactive=True)
            file_viewer = gr.Markdown("*Select a file to view data.*")
            
    # State to store room_id for the viewer
    room_id_state = gr.State("")

    def view_research_file(filename, room_id):
        if not room_id or not filename: return "No file selected."
        history = band.get_room_history(room_id)
        for msg in history:
            meta = msg.get("metadata", {})
            if "file" in meta and meta["file"]["name"] == filename:
                return f"### {filename}\n---\n{meta['file']['content']}"
        return "File content not found."

    file_trigger = evidence_files.change(
        view_research_file,
        inputs=[evidence_files, room_id_state],
        outputs=file_viewer
    )

    btn.click(
        run_committee_demo,
        inputs=[company, amount],
        outputs=[room_status, live_feed, decision, executive_summary, evidence_files, room_id_state, collaboration_map, evidence_checklist]
    )

if __name__ == "__main__":
    # Gradio 6.0: Pass css/js to launch()
    # We remove hardcoded server_port to prevent OSError if 7860 is busy
    demo.launch(js=AUTO_SCROLL_JS, css=BOARDROOM_CSS)
