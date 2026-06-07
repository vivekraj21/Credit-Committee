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
        "agent_registry": ["financial_analyst", "risk_officer", "compliance_officer", "chairman"],
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
    """Each agent performs analysis in parallel (simulated sequentially here)."""
    room_id = state["room_id"]
    findings = {}
    for agent_id in state["recruited_agents"]:
        agent = registry.get_agent(agent_id)
        if agent and agent.role != "Chairman":
            # Passing application data for template formatting
            finding = agent.analyze({"application_data": json.dumps(state["application_data"], indent=2)})
            agent.publish_finding(room_id, json.dumps(finding), "analysis")
            findings[agent.name] = finding
            
    return {
        "agent_findings": findings,
        "current_phase": "Analysis"
    }

def detect_conflicts(state: CommitteeState):
    """Chairman (or system) detects disagreements between agents."""
    findings = state["agent_findings"]
    conflicts = []
    
    # Simple logic: Disagreement on recommendation
    recommendations = {name: data.get("recommendation") for name, data in findings.items()}
    
    unique_recs = set(recommendations.values())
    if len(unique_recs) > 1:
        conflicts.append({
            "type": "Recommendation Mismatch",
            "details": recommendations
        })
        
    return {
        "conflicts": conflicts,
        "current_phase": "Conflict Detection"
    }

def consensus_phase(state: CommitteeState):
    """Final decision making."""
    chairman = registry.get_agent("chairman")
    findings = state["agent_findings"]
    conflicts = state["conflicts"]
    
    # Chairman synthesizes a final board resolution
    res_data = {
        "findings": json.dumps(findings, indent=2),
        "conflicts": json.dumps(conflicts, indent=2)
    }
    decision_finding = chairman.analyze(res_data)
    
    # Simulated decision logic based on findings
    outcome = "APPROVE" if not state["conflicts"] else "CONDITIONAL"
    if any(f.get("recommendation") == "REJECT" for f in findings.values()):
        outcome = "REJECT"
        
    decision = {
        "final_outcome": outcome,
        "confidence_score": 0.85,
        "executive_summary": decision_finding.get("findings", "Decision generated."),
        "conditions": "Standard monitoring" if outcome == "CONDITIONAL" else "None"
    }
    
    return {
        "final_decision": decision,
        "current_phase": "Resolution"
    }

def create_committee_graph():
    workflow = StateGraph(CommitteeState)
    
    workflow.add_node("intake", application_intake)
    workflow.add_node("recruit", recruit_core_agents)
    workflow.add_node("analysis", independent_analysis)
    workflow.add_node("conflict_detection", detect_conflicts)
    workflow.add_node("consensus", consensus_phase)
    
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "recruit")
    workflow.add_edge("recruit", "analysis")
    workflow.add_edge("analysis", "conflict_detection")
    workflow.add_edge("conflict_detection", "consensus")
    workflow.add_edge("consensus", END)
    
    return workflow.compile()
