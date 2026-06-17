from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.graph.state import CommitteeState
from src.agents.registry import registry
from src.collaboration.band_wrapper import band
import json

KEY_VOTERS = ["Financial Analyst", "Compliance Officer", "Credit Risk Officer"]
REQUIRED_VOTERS = ["Financial Analyst", "Compliance Officer"]
FINAL_VOTES = {"APPROVE", "REJECT", "CAUTION"}


def application_intake(state: CommitteeState):
    app_data = state["application_data"]
    room_id = band.create_room(app_data.get("id", "temp-id"))
    return {
        "room_id": room_id,
        "current_phase": "Intake",
        "vote_ledger": {},
        "agent_registry": ["financial_analyst", "credit_risk_officer", "compliance_officer", "research_specialist", "chairman"],
        "committee_events": [{"role": "system", "content": f"Room created: {room_id}"}]
    }


def recruit_core_agents(state: CommitteeState):
    room_id = state["room_id"]
    for agent_id in state["agent_registry"]:
        agent = registry.get_agent(agent_id)
        if agent:
            agent.join_room(room_id)
    return {"current_phase": "Recruitment", "recruited_agents": state["agent_registry"].copy()}


def _run_and_publish(agent, room_id, data):
    finding = agent.analyze(data)
    text = finding.get("findings") or finding.get("summary") or str(finding)
    meta = {"finding_type": "debate"}
    if "file_data" in finding:
        meta["file"] = finding["file_data"]
    agent.publish_finding(room_id, text, metadata=meta)
    return finding


def _get_history_str(room_id):
    return "\n".join([f"{m['sender']}: {m['text'][:200]}" for m in band.get_room_history(room_id)])


def _get_vote(findings, agent_name):
    return findings.get(agent_name, {}).get("recommendation", "NOT VOTED YET")


def independent_analysis(state: CommitteeState):
    room_id = state["room_id"]
    findings = state.get("agent_findings", {})
    for agent_id in ["financial_analyst", "credit_risk_officer", "compliance_officer"]:
        agent = registry.get_agent(agent_id)
        if not agent:
            continue
        finding = _run_and_publish(agent, room_id, {
            "application_data": state["application_data"],
            "room_history": _get_history_str(room_id) or "No history yet."
        })
        findings[agent.name] = finding
        print(f"[ANALYSIS] {agent.name} -> {finding.get('recommendation','?')}")
    return {"agent_findings": findings, "current_phase": "Initial Analysis"}


def debate_round(state: CommitteeState):
    room_id = state["room_id"]
    findings = dict(state.get("agent_findings", {}))

    print(f"\n[DEBATE_START] votes: { {n: _get_vote(findings,n) for n in KEY_VOTERS} }")

    for agent_id in ["financial_analyst", "credit_risk_officer", "compliance_officer", "research_specialist"]:
        agent = registry.get_agent(agent_id)
        if not agent:
            continue
        if agent_id != "research_specialist":
            prev = _get_vote(findings, agent.name)
            if prev in FINAL_VOTES:
                print(f"[SKIP] {agent.name} already voted {prev}")
                continue
            print(f"[RUN] {agent.name} (current: {prev})")
        finding = _run_and_publish(agent, room_id, {
            "application_data": state["application_data"],
            "room_history": _get_history_str(room_id),
            "company_name": state["application_data"].get("company_name", "the company")
        })
        findings[agent.name] = finding
        if agent_id != "research_specialist":
            print(f"[VOTED] {agent.name} -> {finding.get('recommendation','?')}")

    print(f"[DEBATE_END] votes: { {n: _get_vote(findings,n) for n in KEY_VOTERS} }")
    return {"agent_findings": findings, "current_phase": "Board Debate"}


def detect_conflicts(state: CommitteeState):
    room_id = state["room_id"]
    findings = state.get("agent_findings", {})
    chairman = registry.get_agent("chairman")

    ledger = {name: _get_vote(findings, name) for name in KEY_VOTERS}
    print(f"\n[CHAIRMAN_LEDGER] {ledger}")

    # PYTHON decides if we have enough votes to resolve LLM cannot be trusted for this
    required_all_voted = all(ledger.get(name, "") in FINAL_VOTES for name in REQUIRED_VOTERS)
    print(f"[RESOLVE_CHECK] required_all_voted={required_all_voted}")

    if required_all_voted:
        # PYTHON computes majority — LLM is only used for the closing message
        vote_counts: Dict[str, int] = {}
        for name in KEY_VOTERS:
            v = ledger.get(name, "")
            if v in FINAL_VOTES:
                vote_counts[v] = vote_counts.get(v, 0) + 1
        outcome = max(vote_counts, key=vote_counts.get) if vote_counts else "CAUTION"

        ledger_str = "\n".join([f"{n}: {v}" for n, v in ledger.items()])
        analysis = chairman.analyze({
            "application_data": state["application_data"],
            "room_history": (
                f"VOTE LEDGER (all votes are final):\n{ledger_str}\n\n"
                f"The majority outcome is {outcome}. "
                f"Write exactly 1 professional sentence confirming this outcome as final."
            )
        })
        msg = analysis.get("message") or analysis.get("findings") or f"Board has reached a decision: {outcome}."
        print(f"[RESOLVE] outcome={outcome} msg={msg}")
        chairman.message_room(room_id, msg)
        return {
            "consensus_summary": {"action": "RESOLVE", "message": msg, "final_outcome": outcome},
            "current_phase": "Chairman Review",
            "is_consensus_reached": True
        }
    else:
        pending = [n for n in REQUIRED_VOTERS if ledger.get(n, "") not in FINAL_VOTES]
        msg = f"Still waiting on a vote from: {', '.join(pending)}."
        print(f"[DEBATE] pending={pending}")
        chairman.message_room(room_id, msg)
        return {
            "consensus_summary": {"action": "DEBATE", "message": msg, "final_outcome": "PENDING"},
            "current_phase": "Chairman Review",
            "is_consensus_reached": False
        }


def final_resolution(state: CommitteeState):
    summary = state["consensus_summary"]
    return {
        "final_decision": {
            "final_outcome": summary.get("final_outcome", "PENDING"),
            "confidence_score": 0.9,
            "executive_summary": summary.get("message", "Final board decision reached."),
            "conditions": "Standard policy terms."
        },
        "current_phase": "Final Resolution"
    }


def should_continue_debate(state: CommitteeState):
    return "consensus" if state.get("is_consensus_reached") else "debate"


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
    workflow.add_conditional_edges("review", should_continue_debate, {"debate": "debate", "consensus": "consensus"})
    workflow.add_edge("consensus", END)
    return workflow.compile()
