from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.graph.state import CommitteeState
from src.agents.registry import registry
from src.collaboration.band_wrapper import band
import json

def application_intake(state: CommitteeState):
    """Initializes the process by setting up the Band room."""
    app_data = state["application_data"]
    app_id = app_data.get("id", "temp-id")
    room_id = band.create_room(app_id)
    
    return {
        "room_id": room_id,
        "current_phase": "Intake",
        "agent_registry": ["financial_analyst", "risk_officer", "compliance_officer", "research_specialist", "chairman"],
        "committee_events": [{"role": "system", "content": f"Room created: {room_id}"}]
    }

def recruit_core_agents(state: CommitteeState):
    """Signals core agents to join the room."""
    room_id = state["room_id"]
    for agent_id in state["agent_registry"]:
        agent = registry.get_agent(agent_id)
        if agent:
            agent.join_room(room_id)
    
    return {
        "current_phase": "Recruitment",
        "recruited_agents": state["agent_registry"].copy()
    }

def independent_analysis(state: CommitteeState):
    """Phase 1: Basic analysis with initial messaging."""
    room_id = state["room_id"]
    findings = state.get("agent_findings", {})
    
    # All core agents perform their first look
    target_agents = ["financial_analyst", "credit_risk_officer", "compliance_officer"]
    for agent_id in target_agents:
        agent = registry.get_agent(agent_id)
        if not agent: continue
    
        history = band.get_room_history(room_id)
        history_str = "\n".join([f"{m['sender']}: {m['text']}" for m in history])
        
        data = {
            "application_data": state["application_data"],
            "room_history": history_str or "No history yet."
        }
        
        finding = agent.analyze(data)
        agent.publish_finding(room_id, json.dumps(finding), metadata={"finding_type": "analysis"})
        findings[agent.name] = finding
            
    return {
        "agent_findings": findings,
        "current_phase": "Initial Analysis"
    }

def debate_round(state: CommitteeState):
    """Phase 2: Agents react to each other via Band."""
    room_id = state["room_id"]
    findings = state.get("agent_findings", {})
    
    # Order: Analysts ask -> Specialists Answer
    target_agents = ["financial_analyst", "credit_risk_officer", "compliance_officer", "research_specialist"]
    
    for agent_id in target_agents:
        agent = registry.get_agent(agent_id)
        if not agent: continue
        
        history = band.get_room_history(room_id)
        history_str = "\n".join([f"{m['sender']}: {m['text']}" for m in history])
        
        data = {
            "application_data": state["application_data"],
            "room_history": history_str,
            "company_name": state["application_data"].get("company_name", "the company")
        }
        
        finding = agent.analyze(data)
        speaker_output = finding.get("findings") or finding.get("summary") or str(finding)
        
        # Publish to Band with potential file metadata
        metadata = {"finding_type": "debate"}
        if "file_data" in finding:
            metadata["file"] = finding["file_data"]
            
        agent.publish_finding(room_id, speaker_output, metadata=metadata)
        findings[agent.name] = finding
        
    return {
        "agent_findings": findings,
        "current_phase": "Board Debate"
    }

def detect_conflicts(state: CommitteeState):
    """Chairman observes the room and decides if research is complete."""
    room_id = state["room_id"]
    findings = state["agent_findings"]
    
    chairman = registry.get_agent("chairman")
    history = band.get_room_history(room_id)
    history_str = "\n".join([f"{m['sender']}: {m['text']}" for m in history])
    
    data = {
        "application_data": state["application_data"],
        "findings": json.dumps(findings, indent=2),
        "room_history": history_str
    }
    
    analysis = chairman.analyze(data)
    chairman.message_room(room_id, analysis.get("message", "Reviewing board progress."))
    
    # termination logic based on Chairman's explicit action
    is_consensus = str(analysis.get("action", "")).upper() == "RESOLVE"
    
    return {
        "consensus_summary": analysis,
        "current_phase": "Chairman Review",
        "is_consensus_reached": is_consensus
    }

def final_resolution(state: CommitteeState):
    """Phase 3: Formalizing the decision."""
    summary = state["consensus_summary"]
    findings = state["agent_findings"]
    
    outcome = summary.get("final_outcome", "PENDING")
    
    decision = {
        "final_outcome": outcome,
        "confidence_score": 0.9,
        "executive_summary": summary.get("message", "Final board decision reached."),
        "conditions": "Standard policy terms."
    }
    
    return {
        "final_decision": decision,
        "current_phase": "Final Resolution"
    }

def should_continue_debate(state: CommitteeState):
    if state.get("is_consensus_reached"):
        return "consensus"
    return "debate"

def create_committee_graph():
    workflow = StateGraph(CommitteeState)
    
    workflow.add_node("intake", application_intake)
    workflow.add_node("recruit", recruit_core_agents)
    workflow.add_node("analysis", independent_analysis)
    workflow.add_node("debate", debate_round)
    workflow.add_node("review", detect_conflicts)
    workflow.add_node("consensus", final_resolution)
    
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "recruit")
    workflow.add_edge("recruit", "analysis")
    workflow.add_edge("analysis", "debate")
    workflow.add_edge("debate", "review")
    
    # Conditional loop for real debate
    workflow.add_conditional_edges(
        "review",
        should_continue_debate,
        {
            "debate": "debate",
            "consensus": "consensus"
        }
    )
    workflow.add_edge("consensus", END)
    
    return workflow.compile()
