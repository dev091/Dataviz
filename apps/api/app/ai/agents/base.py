from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentStep:
    agent: str
    status: str = "pending"
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def start(self) -> None:
        self.status = "running"
        self.started_at = utc_now_iso()

    def complete(self, output: dict[str, Any] | None = None) -> None:
        self.status = "success"
        self.finished_at = utc_now_iso()
        if output is not None:
            self.output = output

    def fail(self, error: Exception | str) -> None:
        self.status = "failed"
        self.finished_at = utc_now_iso()
        self.error = str(error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "input": self.input,
            "output": self.output,
            "error": self.error,
        }


class BaseAgent:
    name: str = "base_agent"

    def make_step(self, input_data: dict[str, Any] | None = None) -> AgentStep:
        return AgentStep(agent=self.name, input=input_data or {})
