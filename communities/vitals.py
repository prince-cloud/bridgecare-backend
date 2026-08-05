"""
Derived clinical values and vitals helpers.

Covers two things agreed in the 13 July 2026 review:

  * BMI is calculated automatically from height and weight rather than typed in.
  * Blood pressure is free text so "120/80" can be entered exactly as measured,
    but is still parsed for reporting and range checks.

Both work off `InterventionField.field_key`, so they apply to any intervention
whose organiser tagged its height/weight/BP fields — no hard-coded field names.
"""

import re
from typing import Dict, Optional, Tuple

BP_PATTERN = re.compile(r"^\s*(\d{2,3})\s*[/\\\-]\s*(\d{2,3})\s*$")


def calculate_bmi(height_cm, weight_kg) -> Optional[float]:
    """
    BMI in kg/m², rounded to one decimal. Returns None when either input is
    missing or outside a plausible human range.
    """
    try:
        height = float(height_cm)
        weight = float(weight_kg)
    except (TypeError, ValueError):
        return None

    # Guard against unit mix-ups (metres typed instead of centimetres) and
    # transcription slips, which would otherwise produce absurd BMIs.
    if not (50 <= height <= 260):
        return None
    if not (2 <= weight <= 400):
        return None

    metres = height / 100
    return round(weight / (metres * metres), 1)


def bmi_category(bmi: Optional[float]) -> Optional[str]:
    """WHO adult BMI classification. Informational only — not a diagnosis."""
    if bmi is None:
        return None
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


def parse_blood_pressure(value: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Split a "120/80" style reading into (systolic, diastolic).

    Returns (None, None) for anything unparseable — the stored text is never
    rejected, so an unusual note like "not taken" is preserved as entered.
    """
    if not value:
        return None, None

    match = BP_PATTERN.match(str(value))
    if not match:
        return None, None

    systolic, diastolic = int(match.group(1)), int(match.group(2))
    if systolic <= diastolic:
        # Almost certainly transposed or a typo; do not silently "fix" it.
        return None, None
    return systolic, diastolic


def blood_pressure_category(value: str) -> Optional[str]:
    """Coarse BP banding for reporting, following common clinical cut-offs."""
    systolic, diastolic = parse_blood_pressure(value)
    if systolic is None:
        return None
    if systolic < 90 or diastolic < 60:
        return "Low"
    if systolic < 120 and diastolic < 80:
        return "Normal"
    if systolic < 130 and diastolic < 80:
        return "Elevated"
    if systolic < 140 or diastolic < 90:
        return "Hypertension Stage 1"
    if systolic < 180 and diastolic < 120:
        return "Hypertension Stage 2"
    return "Hypertensive Crisis"


def apply_derived_values(
    values_by_key: Dict[str, str],
) -> Dict[str, str]:
    """
    Compute every derived value the platform knows about.

    Takes a {field_key: raw_value} mapping and returns the derived entries to
    store alongside it. Currently BMI from height + weight.
    """
    derived: Dict[str, str] = {}

    bmi = calculate_bmi(values_by_key.get("height"), values_by_key.get("weight"))
    if bmi is not None:
        derived["bmi"] = str(bmi)

    return derived
