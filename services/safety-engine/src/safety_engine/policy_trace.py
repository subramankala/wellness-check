from __future__ import annotations

from shared_types import PolicyTraceEntry


class PolicyTraceCollector:
    def __init__(self) -> None:
        self._entries: list[PolicyTraceEntry] = []

    def record(self, *, stage: str, rule_name: str, matched: bool, detail: str) -> None:
        self._entries.append(
            PolicyTraceEntry(stage=stage, rule_name=rule_name, matched=matched, detail=detail)
        )

    def entries(self) -> list[PolicyTraceEntry]:
        return list(self._entries)
