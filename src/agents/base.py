import os
import json
import uuid
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Find project root dynamically relative to this file to load .env reliably
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(ENV_PATH)

from langchain_groq import ChatGroq
from src.collaboration.band_wrapper import band

# Max characters of history to feed into any prompt — keeps tokens low
HISTORY_TOKEN_LIMIT = 1800

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
        self.custom_prompt = config.get("prompt", "")

        # Initialize LLM: prefer GROQ if configured, otherwise fall back to OpenAI when available.
        groq_key = os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if groq_key:
            try:
                groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
                self.llm = ChatGroq(model_name=groq_model, temperature=0.1)
                print(f"[LLM] Using GROQ provider (ChatGroq) model={groq_model}")
            except Exception as e:
                print(f"[LLM_ERROR] Failed to initialize ChatGroq: {e}")
                self.llm = None
        elif openai_key:
            try:
                # Lazy import for OpenAI chat model
                try:
                    from langchain.chat_models import ChatOpenAI
                except Exception:
                    # Fallback import path for some langchain distributions
                    from langchain_openai.chat_models import ChatOpenAI

                openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
                self.llm = ChatOpenAI(temperature=0.1, model_name=openai_model)
                print(f"[LLM] Using OpenAI provider (ChatOpenAI) model={openai_model}")
            except Exception as e:
                print(f"[LLM_ERROR] Failed to initialize ChatOpenAI: {e}")
                self.llm = None
        else:
            print("[LLM] No GROQ or OpenAI API key found. LLM calls will fail until one is provided.")
            self.llm = None

        # Research Tools (Only for Specialist)
        self.tools = []
        if "research" in self.id.lower() and os.getenv("TAVILY_API_KEY"):
            try:
                from langchain_community.tools.tavily_search import TavilySearchResults
                self.tools = [TavilySearchResults()]
            except:
                pass

    def _truncate_history(self, history: str) -> str:
        """Keep only the tail of history to stay within token limits."""
        if len(history) > HISTORY_TOKEN_LIMIT:
            return "[...earlier messages...]\n" + history[-HISTORY_TOKEN_LIMIT:]
        return history

    def _generate_system_prompt(self, room_history: str, application_data: str = "") -> str:
        """V12: Short, punchy, human-like prompts with history truncation."""
        room_history = self._truncate_history(room_history)

        if self.custom_prompt:
            try:
                return self.custom_prompt.format(
                    room_history=room_history,
                    application_data=application_data,
                    required_paper=self.required_paper,
                    personality=self.personality
                )
            except Exception as e:
                print(f"[PROMPT_ERROR] Failed to format custom prompt for {self.name}: {e}")
                return self.custom_prompt + f"\n\nBOARD HISTORY:\n{room_history}"

        # Check if data already exists in history (for the STOP instruction below)
        data_present = f"Structured {self.required_paper}" in room_history

        if data_present:
            vote_instruction = f"The {self.required_paper} data IS in the history. Give your final vote (APPROVE, REJECT, or CAUTION) with a brief, professional 1-sentence reasoning. Do not mention the specialist."
        else:
            vote_instruction = f"The {self.required_paper} data is missing. Request it from the research specialist by outputting: '@ResearchSpecialist {self.required_paper} - please check the history or run a search for this company.' You MUST set your recommendation to PENDING."

        return f"""You are {self.name}, acting as the {self.role} in a professional corporate credit committee.

SITUATION: {vote_instruction}

STRICT INSTRUCTIONS:
- Write exactly 1 or 2 natural, conversational sentences in "findings".
- Keep it highly professional and direct, like a real human boardroom member.
- NEVER write JSON, curly braces, code blocks, or bullet points inside "findings".
- If requesting data, you MUST include the exact trigger '@ResearchSpecialist {self.required_paper}'.

COMPANY INFO: {application_data}

RECENT BOARD HISTORY:
{room_history}

Reply ONLY in this exact JSON format (do not include any other text):
{{
  "recommendation": "APPROVE or REJECT or CAUTION or PENDING",
  "findings": "Write your conversational finding or request here.",
  "confidence": 0.85
}}"""

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """V12 Analysis with Research Specialist dedup and history truncation."""
        history = data.get("room_history", "")
        app_data = data.get("application_data", {})
        if isinstance(app_data, str):
            try: app_data = json.loads(app_data)
            except: app_data = {}

        # ── Research Specialist Logic ──────────────────────────────────────────
        if "research" in self.id.lower():
            # Scan history for all requests containing @ResearchSpecialist
            requested_categories = []
            for line in history.split("\n"):
                if "@ResearchSpecialist" in line:
                    for cat in ["FINANCIALS", "NEWS", "COMPLIANCE", "INDUSTRY"]:
                        if cat in line.upper() and cat not in requested_categories:
                            requested_categories.append(cat)
            
            # Find the first one that is NOT yet fulfilled
            target_cat = None
            for cat in requested_categories:
                if f"Structured {cat}" not in history:
                    target_cat = cat
                    break
            
            if target_cat:
                company = app_data.get("company_name", "the company")
                return self._execute_clinical_search(f"{target_cat} for {company}", "Agent", company)
            
            if requested_categories:
                return {"summary": "All requested reports have been delivered and are in the Evidence sidebar.", "confidence": 1.0}
            return {"summary": "Standing by — waiting for a specific category request.", "confidence": 0.0}

        # ── Standard Agent Logic ───────────────────────────────────────────────
        print(f"[{self.name}] Checking for {self.required_paper} in historical reports...")
        if self.required_paper != "NONE" and f"Structured {self.required_paper}" in history:
            print(f"[{self.name}] SKIP: Required data {self.required_paper} found. Proceeding to vote.")

        # Extract just company name for the prompt (keep it small)
        company_snippet = f"Company: {app_data.get('company_name', 'Unknown')}, Loan: ${app_data.get('requested_amount', '?')}M"

        prompt = self._generate_system_prompt(history, company_snippet)

        # If LLM wasn't initialized (no GROQ/OPENAI keys), return a safe pending response
        if not self.llm:
            print(f"[LLM_MISSING] {self.name} cannot run analysis — no LLM configured.")
            return {"recommendation": "PENDING", "findings": "LLM not configured; provide GROQ_API_KEY or OPENAI_API_KEY.", "confidence": 0.0}

        try:
            response = self.llm.invoke(prompt)
            return self._parse_json_response(response.content)
        except Exception as e:
            if "401" in str(e):
                print(f"[API_ERROR] GROQ API Key is INVALID (401). Please check GROQ_API_KEY in .env")
                return {"recommendation": "ERROR", "findings": "API key issue — check terminal.", "confidence": 0.0}
            print(f"[AGENT_CRASH] {self.name} failed: {str(e)}")
            raise e

    def _execute_clinical_search(self, query: str, requester: str, company: str) -> Dict[str, Any]:
        """Tavily search — one shot, one file."""
        category = "GENERAL"
        for cat in ["FINANCIALS", "NEWS", "COMPLIANCE", "INDUSTRY"]:
            if cat in query.upper(): category = cat; break

        if not self.tools:
            return {"summary": f"Search tool unavailable for {category}.", "confidence": 0.0}

        try:
            print(f"[TAVILY_LOG] Searching {category} for {company}...")
            raw_results = self.tools[0].invoke(query)
            filename = f"{category.lower()}_{uuid.uuid4().hex[:4]}.json"

            # Try to extract a usable URL from the Tavily results so the frontend can link to the original source.
            def _find_first_url(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                            return v
                        res = _find_first_url(v)
                        if res: return res
                elif isinstance(obj, list):
                    for it in obj:
                        res = _find_first_url(it)
                        if res: return res
                return None

            file_url = _find_first_url(raw_results)

            file_meta = {"name": filename, "content": json.dumps(raw_results, indent=2), "type": "application/json", "category": category}
            if file_url:
                file_meta["url"] = file_url

            return {
                "summary": f"@{requester} Structured {category} data now in Evidence sidebar as {filename}.",
                "file_data": file_meta,
                "confidence": 1.0
            }
        except Exception as e:
            if "401" in str(e):
                print(f"[API_ERROR] TAVILY API Key is INVALID (401). Please check TAVILY_API_KEY in .env")
                return {"summary": f"Tavily API Key Invalid.", "confidence": 0.0}
            print(f"[TAVILY_CRASH] Search failed: {str(e)}")
            return {"summary": f"Search failed: {str(e)}", "confidence": 0.0}

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        try:
            cleaned = content.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            return json.loads(cleaned)
        except Exception:
            # Fallback line-by-line parser for text key-value pairs
            parsed = {}
            for line in content.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    k = parts[0].strip().replace('"', '').replace("'", "").lower()
                    v = parts[1].strip().replace('"', '').replace("'", "")
                    if v.endswith(","):
                        v = v[:-1].strip()
                    parsed[k] = v
            
            # If we extracted keys, map/return them
            if parsed:
                # Ensure findings/message keys exist
                if "findings" not in parsed and "message" in parsed:
                    parsed["findings"] = parsed["message"]
                if "message" not in parsed and "findings" in parsed:
                    parsed["message"] = parsed["findings"]
                return parsed
                
            return {"recommendation": "CAUTION", "findings": content[:300], "confidence": 0.5}

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
