import os
import uuid
from typing import List, Dict, Any
from dotenv import load_dotenv
import requests

load_dotenv()

class BandWrapper:
    """
    Abstraction layer for Band Protocol concepts.
    Demonstrates Room Creation, Agent Presence, Shared Context, and Messaging.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("BAND_API_KEY")
        self.base_url = "https://api.band.ai/v1" # Placeholder for Band API URL
        self.active_rooms = {}

    def create_room(self, application_id: str) -> str:
        """Creates a Band room for a specific loan application."""
        room_id = f"credit-committee-room-{application_id}"
        self.active_rooms[room_id] = {
            "agents": [],
            "messages": [],
            "context": {}
        }
        print(f"[BAND] Created room: {room_id}")
        return room_id

    def join_agent(self, room_id: str, agent_name: str):
        """Simulates an agent joining a Band room."""
        if room_id in self.active_rooms:
            if agent_name not in self.active_rooms[room_id]["agents"]:
                self.active_rooms[room_id]["agents"].append(agent_name)
                print(f"[BAND] {agent_name} joined room {room_id}")
                self.send_message(room_id, "System", f"{agent_name} joined the room.")

    def send_message(self, room_id: str, sender: str, message: str, metadata: Dict[str, Any] = None):
        """Sends a message to the Band room."""
        if room_id in self.active_rooms:
            msg_obj = {
                "id": str(uuid.uuid4()),
                "sender": sender,
                "text": message,
                "metadata": metadata or {},
                "timestamp": str(uuid.uuid4()) # Placeholder for real timestamp
            }
            self.active_rooms[room_id]["messages"].append(msg_obj)
            print(f"[BAND] Message in {room_id} from {sender}: {message}")
            return msg_obj

    def update_context(self, room_id: str, key: str, value: Any):
        """Updates shared room context."""
        if room_id in self.active_rooms:
            self.active_rooms[room_id]["context"][key] = value
            print(f"[BAND] Context updated in {room_id}: {key}")

    def get_room_history(self, room_id: str) -> List[Dict[str, Any]]:
        """Retrieves message history from the Band room."""
        return self.active_rooms.get(room_id, {}).get("messages", [])

    def get_room_context(self, room_id: str) -> Dict[str, Any]:
        """Retrieves shared context from the Band room."""
        return self.active_rooms.get(room_id, {}).get("context", {})

# Global instance for the hackathon prototype
band = BandWrapper()
