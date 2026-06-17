from typing import Annotated, TypedDict, List, Dict, Any, Union
from langgraph.graph.message import add_messages

class CommitteeState(TypedDict):
    """
    Centralized state object for the Corporate Credit Committee.
    """
    # Core Application Data
    application_data: Dict[str, Any]
    
    # Band Room Context
    room_id: str
    
    # Registry & Participation
    agent_registry: List[str]
    recruited_agents: List[str]
    
    # Findings & Debate
    agent_findings: Dict[str, Any] # Map of AgentName -> FindingData
    agent_messages: List[Dict[str, str]] # Messages sent via Band
    debate_history: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    
    # Consensus & Resolution
    consensus_summary: Dict[str, Any]
    final_decision: Dict[str, Any]
    confidence_score: float
    
    # Events & RAG
    committee_events: Annotated[List[Dict[str, Any]], add_messages]
    policy_references: List[str]
    
    # Internal Flow State
    current_phase: str
    is_consensus_reached: bool
    needs_dynamic_recruitment: bool
    # Live vote ledger: {"Financial Analyst": "APPROVE", "Compliance Officer": "CAUTION", ...}
    vote_ledger: Dict[str, str]
