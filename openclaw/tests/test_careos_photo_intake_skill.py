from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "openclaw/skills/careos-photo-intake/scripts/run.py"

spec = importlib.util.spec_from_file_location("careos_photo_intake_run", SKILL_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_parse_photo_text_after_food_pm() -> None:
    parsed = module.parse_photo_text("Aztor 40mg 1 tab after food at 9 PM")
    assert parsed.medication_name == "AZTOR"
    assert parsed.scheduled_time == "21:00"
    assert parsed.meal_constraint == "after_meal"


def test_parse_photo_text_before_food_am() -> None:
    parsed = module.parse_photo_text("Pantop 40mg before food 7 AM")
    assert parsed.scheduled_time == "07:00"
    assert parsed.meal_constraint == "before_meal"
