from __future__ import annotations

from protocols_lib import ProtocolDefinition, load_protocol


def load_protocol_for_request(protocol_id: str) -> ProtocolDefinition:
    return load_protocol(protocol_id=protocol_id)
