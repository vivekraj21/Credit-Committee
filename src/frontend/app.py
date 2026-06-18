import gradio as gr
import requests
import json
import uuid
import time
import sys
import os

# Set output encoding to UTF-8 to prevent unicode print errors on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Ensure project root is in sys.path to allow absolute imports from 'src'
# The root is the parent of the 'src' directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# V7 Ultra-Compact Professional Boardroom
from src.graph.graph import create_committee_graph
from src.collaboration.band_wrapper import band
from src.agents.registry import registry, reset_global_registry_instances

print(f"--- 🔑 RUNTIME KEY CHECK ---")
print(f"GROQ_KEY: {str(os.getenv('GROQ_API_KEY'))[:8]}...")
print(f"TAVILY_KEY: {str(os.getenv('TAVILY_API_KEY'))[:8]}...")
print(f"----------------------------")

BOARDROOM_CSS = """
body { background-color: #f3f2ef; font-family: -apple-system, sans-serif; margin: 0; padding: 0; }
.gradio-container { background-color: #f3f2ef !important; }
.boardroom-container { background: white; border-radius: 8px; border: 1px solid #e0dfdc; padding: 10px; margin-top: 0 !important; max-height: 600px; }

# Ultra-Compact Chat Feed
# Reduce height to ~50% of the boardroom box and add visual separators
# between messages so each agent's messages are easier to distinguish.
# `#chat-feed` max-height kept intentionally conservative for hosted layout.
# Adjust values as needed to taste.
/* chat-feed: increased height by ~25% (from 300px -> 375px) for better readability */
/* chat-feed: increased height by ~25% (from 300px -> 375px) for better readability */
#chat-feed { 
    height: 450px; 
    overflow-y: auto; 
    padding: 10px; 
    display: flex; 
    flex-direction: column; 
    gap: 8px; scroll-behavior: smooth; 
    background: #ffffff;
    border: 1px solid #e0dfdc;
    border-radius: 4px;
}

.chat-msg { display: flex; flex-direction: column; max-width: 95%; padding-bottom: 6px; }
.chat-msg + .chat-msg { border-top: 1px solid #e9eef3; padding-top: 8px; margin-top: 8px; }
.msg-header { display: flex; align-items: center; gap: 4px; margin-bottom: 2px; font-size: 0.7rem; color: #666; }
.agent-status { font-weight: 600; background: #e7f3ff; padding: 0px 6px; border-radius: 10px; color: #0077b5; font-size: 0.6rem; }

.chat-bubble { padding: 8px 12px; border-radius: 0 8px 8px 8px; font-size: 13px; line-height: 1.4; border: 1px solid #e0dfdc; box-shadow: 0 1px 0 rgba(0,0,0,0.02); }
.bubble-agent { background: #f9fafb; color: #333; align-self: flex-start; }
.bubble-chairman { background: #0077b5; color: white; border-color: #0077b5; align-self: flex-start; }
.bubble-system { align-self: center; background: transparent; color: #666; font-size: 11px; padding: 5px; border-top: 1px solid #e0dfdc; width: 100%; text-align: center; }

/* Alternating subtle background per message to visually separate speakers */
#chat-feed .chat-msg:nth-child(odd) .chat-bubble { background: #fbfdff; }
#chat-feed .chat-msg:nth-child(even) .chat-bubble { background: #ffffff; }

h1, h2, h3, p, span, label { color: #333 !important; margin: 0 !important; }
.active-speaker { border-left: 3px solid #0077b5; background: rgba(0, 119, 181, 0.03); }

/* Compact Inputs */
input, textarea { background: #f9fafb !important; border: 1px solid #e0dfdc !important; padding: 4px !important; }
.label-style { font-size: 0.8rem !important; }

/* Runtime keys accordion sizing */
.runtime-accordion { max-height: 200px; overflow-y: auto; padding-right: 8px; }

/* Reduce gap between Search Status header and checklist */
h1 { margin: 0px 0 !important; font-size: 1rem; }
.checklist { margin-top: 0px !important; margin-bottom: 0 !important; padding-left: 8px; }
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
    
    # Try parsing text as JSON in case of raw logs/structural outputs
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            text = parsed.get("findings") or parsed.get("summary") or parsed.get("message") or text
    except:
        pass
        
    status = findings.get(sender, {}).get("recommendation", "PARTICIPATING")
    
    cls = "bubble-agent"
    header_html = f"<div class='msg-header'><span>{sender}</span><span class='agent-status'>{status}</span></div>"
    
    if sender == "System": 
        cls = "bubble-system"
        header_html = ""
    elif sender == "Committee Chairman": 
        cls = "bubble-chairman"
    
    active_cls = "active-speaker" if sender in current_phase or (current_phase == "Board Debate" and sender != "System") else ""
    
    # Add a small separator after each message for clear visual separation.
    return f"""
    <div class=\"chat-msg {active_cls}\">
        {header_html}
        <div class=\"chat-bubble {cls}\">{text}</div>
    </div>
    <div class=\"msg-sep\"></div>
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
    
    yield "...", "", "WAITING", "...", "<div class='evidence-list'>No evidence yet.</div>", "", "<div>Checking...</div>"
    
    try:
        current_state = initial_state
        # Limit rounds for control
        for i, output in enumerate(graph.stream(current_state)):
            node_name = list(output.keys())[0]
            current_state.update(output[node_name])
            
            room_id = current_state.get("room_id", "N/A")
            phase = current_state.get("current_phase", "Debate")
            
            messages = band.get_room_history(room_id)
            findings_map = current_state.get("agent_findings", {})
            # Ensure the chat feed is boxed and scrollable across Gradio versions by
            # including an inline max-height and overflow style on the container.
            # Increased max-height by 20% (approx) to improve readability on hosted Space.
            msg_html = f"<div id='chat-feed' style='max-height:450px; overflow-y:auto;'>{''.join([format_message_v3(m, findings_map, phase) for m in messages])}</div>"
            
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

            files = [m["metadata"]["file"] for m in messages if "file" in m.get("metadata", {})]
            
            outcome = current_state.get("final_decision", {})
            decision_text = outcome.get("final_outcome", "PENDING")
            summary = outcome.get("executive_summary", "Board deliberating...")
            
            # Build a simple HTML list showing `name : url` for each uploaded file.
            if files:
                items = []
                for fmeta in files:
                    fname = fmeta.get("name")
                    file_url = fmeta.get("url") or f"/evidence/{fname}"
                    items.append(f"<li>{fname} : <a href='{file_url}' target='_blank'>{file_url}</a></li>")
                evidence_html = f"<div class='evidence-list'><ul>{''.join(items)}</ul></div>"
            else:
                evidence_html = "<div class='evidence-list'>No evidence files uploaded.</div>"

            yield (
                phase, msg_html, decision_text, summary,
                evidence_html,
                room_id, checklist_html
            )
            time.sleep(0.5)

    except Exception as e:
        print(f"[CRITICAL_ERROR] {str(e)}")
        yield ("Error", f"<div class='bubble-system'>Error: {str(e)}</div>", "ERROR", "Halted.", "<div class='evidence-list'>Error</div>", "", "<div>Halted</div>")

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
                with gr.Accordion("⚙️ Runtime Keys & Provider", open=False, elem_classes="runtime-accordion"):
                    provider = gr.Dropdown(label="LLM Provider (auto picks if blank)", choices=["auto","groq","openai"], value="auto")
                    groq_key = gr.Textbox(label="GROQ_API_KEY", placeholder="Paste GROQ key (optional)", lines=1, visible=False)
                    openai_key = gr.Textbox(label="OPENAI_API_KEY", placeholder="Paste OpenAI key (optional)", lines=1, visible=False)
                    band_key = gr.Textbox(label="BAND_API_KEY", placeholder="Band API key (optional)", lines=1)
                    tavily_key = gr.Textbox(label="TAVILY_API_KEY", placeholder="Tavily API key (optional)", lines=1)
                    apply_keys_btn = gr.Button("Apply Keys", variant="secondary")
                    keys_status = gr.Markdown("*Using keys from .env by default.*")

                def apply_runtime_keys(provider_choice, groq_k, openai_k, band_k, tavily_k):
                    # Apply provided keys to the environment; if blank, keep existing .env values
                    changed = []
                    if groq_k:
                        os.environ["GROQ_API_KEY"] = groq_k.strip()
                        changed.append("GROQ_API_KEY")
                    if openai_k:
                        os.environ["OPENAI_API_KEY"] = openai_k.strip()
                        changed.append("OPENAI_API_KEY")
                    if band_k:
                        os.environ["BAND_API_KEY"] = band_k.strip()
                        band.set_api_key(band_k.strip())
                        changed.append("BAND_API_KEY")
                    if tavily_k:
                        os.environ["TAVILY_API_KEY"] = tavily_k.strip()
                        changed.append("TAVILY_API_KEY")

                    # Provider preference: allow forcing provider when chosen
                    if provider_choice and provider_choice != "auto":
                        os.environ["LLM_PROVIDER"] = provider_choice
                        changed.append("LLM_PROVIDER")

                    # Reset registry so agents reinitialize with new keys
                    reset_global_registry_instances()

                    msg = "Applied: " + (", ".join(changed) if changed else "(no changes, using .env)")
                    return msg


                apply_keys_btn.click(
                    apply_runtime_keys,
                    inputs=[provider, groq_key, openai_key, band_key, tavily_key],
                    outputs=[keys_status]
                )


                def provider_changed(choice):
                    # Hide/show key fields depending on chosen provider
                    if choice == "groq":
                        return gr.update(visible=True), gr.update(visible=False)
                    elif choice == "openai":
                        return gr.update(visible=False), gr.update(visible=True)
                    else:
                        # 'auto' -> hide both to avoid showing key fields until user selects provider
                        return gr.update(visible=False), gr.update(visible=False)


                provider.change(provider_changed, inputs=[provider], outputs=[groq_key, openai_key])
            
            # --- Status Check ---
            gr.Markdown("#### 📋 Search Status")
            evidence_checklist = gr.HTML("<div class='checklist'>Ready for autonomous research.</div>")

        with gr.Column(scale=3):
            room_status = gr.Markdown("#### 🏠 Live Boardroom Feed")
            live_feed = gr.HTML("<div id='chat-feed'><div class='bubble-system'>Enter request details to begin.</div></div>")

        with gr.Column(scale=1):
            gr.Markdown("#### ⚖️ Resolution")
            decision = gr.Label(label="Board Vote", value="WAITING")
            executive_summary = gr.Markdown("#### Summary\n*Evidence-based analysis pending.*")
            
            gr.Markdown("---")
            gr.Markdown("#### 📂 Evidence")
            # Show evidence items as a simple name : url list (no full file bodies displayed)
            evidence_list = gr.HTML("<div class='evidence-list'>No evidence yet.</div>")
            
    # State to store room_id for the viewer
    room_id_state = gr.State("")
    
    # We intentionally do not expose full file contents in the UI. Evidence is displayed
    # as a simple list in `evidence_list` (name : url). No change handlers required.

    btn.click(
        run_committee_demo,
        inputs=[company, amount],
        outputs=[room_status, live_feed, decision, executive_summary, evidence_list, room_id_state, evidence_checklist],
        concurrency_limit=1
    )

if __name__ == "__main__":
    # Gradio 6.0: Pass css/js to launch()
    # Queue with max_size=1 ensures only one committee session runs at a time.
    demo.queue(max_size=1)
    demo.launch(js=AUTO_SCROLL_JS, css=BOARDROOM_CSS)
