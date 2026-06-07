from typing import List, Dict, Any, Optional
from src.collaboration.band_wrapper import band
from langchain_groq import ChatGroq
import os
import json
from dotenv import load_dotenv

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
        self.description = config["description"]
        self.prompt_template = config["prompt"]
        
        # LLM setup based on provider
        provider = config.get("llm_provider", "groq")
        if provider == "groq":
            self.llm = ChatGroq(
                temperature=config.get("temperature", 0.2),
                model_name=config.get("model", "llama3-70b-8192"),
                groq_api_key=os.getenv("GROQ_API_KEY")
            )
        else:
            # Placeholder for other providers like OpenAI
            self.llm = None

    def analyze(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Performs analysis using the prompt template from the config."""
        # Format the prompt using the provided data
        # Note: In a real scenario, we might needs more complex data mapping
        formatted_prompt = self.prompt_template.format(**data)
        
        response = self.llm.invoke(formatted_prompt)
        
        try:
            # Attempt to parse JSON from the response
            finding = json.loads(response.content)
        except:
            # Fallback if LLM output is not clean JSON
            finding = {
                "recommendation": "CAUTION",
                "findings": response.content,
                "status": "Incomplete JSON Parse"
            }
        
        return finding

    def publish_finding(self, room_id: str, content: str, finding_type: str = "analysis"):
        """Publishes a finding to the Band room."""
        band.send_message(room_id, self.name, content, {"finding_type": finding_type})
        return {"agent": self.name, "type": finding_type, "content": content}

    def message_room(self, room_id: str, text: str):
        """Sends a regular message to the Band room."""
        band.send_message(room_id, self.name, text)

    def join_room(self, room_id: str):
        """Joins the Band room."""
        band.join_agent(room_id, self.name)
