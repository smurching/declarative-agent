"""Declarative agent configuration and loading."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import yaml
from pathlib import Path


class AgentConfig(BaseModel):
    """Configuration for a declarative agent."""

    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")

    # Model configuration
    model: str = Field("databricks-gpt-5-2", description="LLM model to use")
    temperature: float = Field(0.7, description="Temperature for LLM")

    # System instructions
    instructions: Optional[str] = Field(None, description="System instructions for the agent")

    # Agent capabilities
    supports_streaming: bool = Field(True, description="Whether agent supports streaming")
    supports_background: bool = Field(True, description="Whether agent supports background execution")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @classmethod
    def from_yaml(cls, path: Path) -> "AgentConfig":
        """Load agent config from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path):
        """Save agent config to YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)


class DeclarativeAgent:
    """
    A declarative agent defined by configuration.

    Agents are defined via YAML and executed using the OpenResponses API backend.
    """

    def __init__(self, config: AgentConfig, backend_url: str = "http://localhost:8000"):
        """
        Initialize agent.

        Args:
            config: Agent configuration
            backend_url: URL of the OpenResponses API backend
        """
        self.config = config
        self.backend_url = backend_url

    @classmethod
    def from_yaml(cls, path: Path, backend_url: str = "http://localhost:8000") -> "DeclarativeAgent":
        """Load agent from YAML file."""
        config = AgentConfig.from_yaml(path)
        return cls(config, backend_url)

    def get_system_message(self) -> Optional[Dict[str, str]]:
        """Get system message if instructions are defined."""
        if self.config.instructions:
            return {"role": "system", "content": self.config.instructions}
        return None

    def __repr__(self) -> str:
        return f"DeclarativeAgent(name='{self.config.name}', model='{self.config.model}')"
