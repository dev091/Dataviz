from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, *, json_mode: bool = False, temperature: float = 0.1) -> str:
        raise NotImplementedError
