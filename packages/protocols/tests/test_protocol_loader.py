from pathlib import Path

import pytest

from protocols_lib import ProtocolLoadError, load_protocol


def test_valid_protocol_load() -> None:
    protocol = load_protocol("post_op_fever_v1")
    assert protocol.protocol_id == "post_op_fever_v1"
    assert len(protocol.required_questions) >= 1


def test_invalid_protocol_load_missing_fields() -> None:
    protocol_dir = Path("packages/protocols/protocols")
    invalid_path = protocol_dir / "broken_protocol.yaml"
    invalid_path.write_text("protocol_id: broken_protocol\nversion: 1\n", encoding="utf-8")

    try:
        with pytest.raises(ProtocolLoadError):
            load_protocol("broken_protocol")
    finally:
        if invalid_path.exists():
            invalid_path.unlink()
