from __future__ import annotations

from abc import ABC, abstractmethod

from shared_types import ExtractionResult, RuntimeSessionState


class TurnExtractor(ABC):
    @abstractmethod
    def extract(self, utterance: str, session_state: RuntimeSessionState) -> ExtractionResult:
        raise NotImplementedError
