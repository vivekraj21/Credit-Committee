import os
import json
import uuid
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from src.collaboration.band_wrapper import band

load_dotenv()

class BaseAgent:
    """
    Base class for all AI Corporate Credit Committee agents.
    Handles LLM initialization and Band interaction from a JSON config.
    """
    def __init__(self, config: Dict[str, Any]):
        self.id = config["id"]
        self.name = config["name"]
        self.role = config["role"]
        self.required_paper = config.get("required_paper", "NONE")
        self.personality = config.get("personality", "Professional")
        self.few_shot_examples = config.get("few_shot_examples", [])
        
        # Initialize Groq LLM
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.1)
        
        # Research Tools (Only for Specialist)
        self.tools = []
        if "research" in self.id.lower() and os.getenv("TAVILY_API_KEY"):
            try:
                from langchain_community.tools.tavily_search import TavilySearchResults
                self.tools = [TavilySearchResults()]
            except:
                pass

    def _generate_system_prompt(self, room_history: str) -> str:
        """V10 Protocol: One required paper, check Band-History first."""
        return f"""You are {self.name} ({self.role}). 
PERSONALITY: {self.personality}
REQUIRED DATA: {self.required_paper}

STRICT PROTOCOL:
1. READ HISTORY: Check if a JSON report for category '{self.required_paper}' exists.
2. REQUEST: If MISSING, request ONCE: '@ResearchSpecialist {self.required_paper}'.
3. RESOLVE: If PRESENT, summarize evidence and RECOMMEND (APPROVE/REJECT).
4. STOP: Do not repeat requests if data is already available.

BAND HISTORY:
{room_history}

Output ONLY valid JSON:
{{ "recommendation": "DECISION", "findings": "Act 1: Policy... Act 2: @ResearchSpecialist... Act 3: Vote...", "confidence": 1.0 }}
"""

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """V10 Optimized Analysis."""
        history = data.get("room_history", "")
        app_data = data.get("application_data", {})
        if isinstance(app_data, str):
            try: app_data = json.loads(app_data)
            except: app_data = {}
        
        # Specialist Logic
        if "research" in self.id.lower() and "@ResearchSpecialist" in history:
            mentions = history.split("@ResearchSpecialist")
            last_mention = mentions[-1].split("\n")[0].strip()
            
            # Category validation
            target_cat = None
            for cat in ["FINANCIALS", "NEWS", "COMPLIANCE", "INDUSTRY"]:
                if cat in last_mention.upper():
                    target_cat = cat
                    break
            
            if target_cat:
                company = app_data.get("company_name", "the company")
                return self._execute_clinical_search(f"{target_cat} for {company}", "Agent", company)
            else:
                return {"summary": "Awaiting specific category request (FINANCIALS/COMPLIANCE/NEWS).", "confidence": 0.0}

        # Standard Agent Logic
        print(f"[{self.name}] Checking for {self.required_paper} in historical reports...")
        if self.required_paper != "NONE" and f"Structured {self.required_paper}" in history:
            print(f"[{self.name}] SKIP: Required data {self.required_paper} found in Band. Proceeding to vote.")
            # We don't modify history here, we let the prompt handle the vote nudging

        prompt = self._generate_system_prompt(history)
        try:
            response = self.llm.invoke(prompt)
            return self._parse_json_response(response.content)
        except Exception as e:
            if "401" in str(e):
                print(f"[API_ERROR] GROQ API Key is INVALID (401). Please check GROQ_API_KEY in .env")
                return {"recommendation": "ERROR", "findings": "GROQ INVALID API KEY. Check terminal.", "confidence": 0.0}
            print(f"[AGENT_CRASH] {self.name} failed: {str(e)}")
            raise e

    def _execute_clinical_search(self, query: str, requester: str, company: str) -> Dict[str, Any]:
        """Tavily search logic remains clinical."""
        category = "GENERAL"
        for cat in ["FINANCIALS", "NEWS", "COMPLIANCE", "INDUSTRY"]:
            if cat in query.upper(): category = cat; break

        if not self.tools:
            return {"summary": f"@{requester} Search tool unavailable for {category}.", "confidence": 0.0}

        try:
            print(f"[TAVILY_LOG] Searching {category} for {company}...")
            raw_results = self.tools[0].invoke(query)
            filename = f"{category.lower()}_{uuid.uuid4().hex[:4]}.json"
            return {
                "summary": f"@{requester} Structured {category} data now in Evidence sidebar as {filename}.",
                "file_data": {"name": filename, "content": json.dumps(raw_results, indent=2), "type": "application/json"},
                "confidence": 1.0
            }
        except Exception as e:
            if "401" in str(e):
                print(f"[API_ERROR] TAVILY API Key is INVALID (401). Please check TAVILY_API_KEY in .env")
                return {"summary": f"@{requester} ERROR: Tavily API Key Invalid.", "confidence": 0.0}
            print(f"[TAVILY_CRASH] Search failed: {str(e)}")
            return {"summary": f"@{requester} Search failed: {str(e)}", "confidence": 0.0}

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except:
            return {"recommendation": "CAUTION", "findings": content, "confidence": 0.5}

    def publish_finding(self, room_id: str, content: str, finding_type: str = "analysis", metadata: Dict[str, Any] = None):
        """Publishes a finding to the Band room with metadata."""
        final_meta = metadata or {"finding_type": finding_type}
        band.send_message(room_id, self.name, content, final_meta)
        return {"agent": self.name, "type": finding_type, "content": content}

    def message_room(self, room_id: str, text: str):
        """Sends a regular message to the Band room."""
        band.send_message(room_id, self.name, text)

    def join_room(self, room_id: str):
        """Joins the Band room."""
        band.join_agent(room_id, self.name)
