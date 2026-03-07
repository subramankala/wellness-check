from __future__ import annotations

from safety_engine.policy_trace import PolicyTraceCollector


HARD_STOP_RULES: dict[str, tuple[str, ...]] = {
    "chest_pain": ("chest pain",),
    "severe_shortness_of_breath": (
        "severe shortness of breath",
        "cannot breathe",
        "can't breathe",
    ),
    "heavy_bleeding": ("heavy bleeding", "bleeding heavily"),
    "confusion": ("confusion", "confused", "disoriented"),
    "uncontrolled_vomiting": (
        "uncontrolled vomiting",
        "vomiting nonstop",
        "cannot stop vomiting",
    ),
}


def detect_hard_stops(text_corpus: str, trace: PolicyTraceCollector) -> list[str]:
    lowered = text_corpus.lower()
    matched_rules: list[str] = []

    for rule_name, terms in HARD_STOP_RULES.items():
        matched = any(term in lowered for term in terms)
        trace.record(
            stage="hard_stop",
            rule_name=rule_name,
            matched=matched,
            detail=f"matched terms: {terms}",
        )
        if matched:
            matched_rules.append(rule_name)

    return matched_rules
