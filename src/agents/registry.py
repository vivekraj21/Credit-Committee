import json
import os
from typing import Dict, List, Optional
from src.agents.base import BaseAgent

class AgentRegistry:
    """
    Registry and Factory for agents.
    Loads agents from a central JSON configuration file.
    """
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default path relative to this file
            config_path = os.path.join(os.path.dirname(__file__), "agents.json")
            
        self.config_path = config_path
        self._agent_configs: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, BaseAgent] = {}
        self.load_configs()

    def load_configs(self):
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                for agent_cfg in data.get("agents", []):
                    self._agent_configs[agent_cfg["id"]] = agent_cfg
        except Exception as e:
            print(f"Error loading agent configs: {e}")

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Returns an instance of the requested agent, creating it if necessary."""
        if agent_id not in self._instances:
            if agent_id in self._agent_configs:
                config = self._agent_configs[agent_id]
                self._instances[agent_id] = BaseAgent(config)
            else:
                return None
        return self._instances.get(agent_id)

    def list_available_agents(self) -> List[str]:
        return list(self._agent_configs.keys())

# Global instance for the system
registry = AgentRegistry()
