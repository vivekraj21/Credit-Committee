from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
from src.graph.graph import create_committee_graph
from src.collaboration.band_wrapper import band
from src.database.db import init_db

app = FastAPI(title="AI Corporate Credit Committee Backend")

# Initialize DB on startup
@app.on_event("startup")
def startup_event():
    init_db()

class LoanApplication(BaseModel):
    id: str
    company_name: str
    industry: str
    country: str
    revenue: float
    requested_amount: float
    debt_ratio: float
    credit_score: int

@app.post("/submit-application")
async def submit_application(application: LoanApplication, background_tasks: BackgroundTasks):
    graph = create_committee_graph()
    initial_state = {
        "application_data": application.dict(),
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
    
    # Run the graph (asynchronous for Demo)
    result = graph.invoke(initial_state)
    return {"status": "processing", "room_id": result["room_id"], "final_result": result["final_decision"]}

@app.get("/room/{room_id}/status")
async def get_room_status(room_id: str):
    return {
        "messages": band.get_room_history(room_id),
        "context": band.get_room_context(room_id)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
