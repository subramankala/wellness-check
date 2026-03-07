from __future__ import annotations

from safety_engine.policy_trace import PolicyTraceCollector


URGENT_RULES: dict[str, tuple[str, ...]] = {
    "wound_redness": ("wound redness", "redness around incision"),
    "persistent_fever": ("persistent fever", "high fever"),
    "worsening_postop_pain": ("worsening pain", "increasing pain"),
}


def detect_urgent_rules(text_corpus: str, trace: PolicyTraceCollector) -> list[str]:
    lowered = text_corpus.lower()
    matched_rules: list[str] = []

    for rule_name, terms in URGENT_RULES.items():
        matched = any(term in lowered for term in terms)
        trace.record(
            stage="urgent",
            rule_name=rule_name,
            matched=matched,
            detail=f"matched terms: {terms}",
        )
        if matched:
            matched_rules.append(rule_name)

    return matched_rules
