#!/usr/bin/env python3
"""
Extract patient data from a Breakthrough Medical consult form PDF.

This script reads a consult/intake PDF from another system and extracts
structured patient data as JSON that can be fed to generate_intake_form.py.

It handles the standard Breakthrough Medical "Weight Loss Medical Consultation"
PDF format with label/value pairs in the text.

Usage:
    python extract_patient_data.py <input_pdf> [--output <output.json>]

If --output is not specified, prints JSON to stdout.
"""

import argparse
import json
import re
import sys

try:
    # PyMuPDF >= 1.24 ships the `pymupdf` name; the legacy `fitz` alias is
    # deprecated and slated for removal, so prefer the modern one.
    import pymupdf as fitz
except ImportError:
    try:
        import fitz  # PyMuPDF < 1.24
    except ImportError:
        print(
            "Error: PyMuPDF is required. Install with: "
            "pip install --break-system-packages PyMuPDF"
        )
        sys.exit(1)


# All known labels in the consult form (labels that appear on their own lines)
# This set is used to distinguish labels from values.
KNOWN_LABELS = {
    "Breakthrough Medical", "Weight Loss Medical Consultation",
    "Client Contact Information", "Medical History", "Medical Conditions",
    "None of the above", "List any other medical conditions",
    "Please list any allergies",
    "Please list any medications you are currently taking including vitamins and dietary supplements",
    "Please list any surgeries you have had",
    "Vitals", "Contraindications (Disqualifiers)",
    "Informed Patient Consent", "HIPPA PRIVACY NOTICE", "RETURN POLICY",
    "First Name", "Middle Name", "Last Name", "Gender", "Birthday",
    "Address 1", "Address 2", "City", "State", "Zipcode",
    "Mobile Phone", "Email", "Emergency Contact", "Contact Relation",
    "Emergency Phone", "Occupation", "Height", "Weight", "Target Weight",
    "You can not receive the medication if you have any of these conditions",
    "Select All That Apply", "None of the Above",
}

# Labels we want to extract values for → JSON key mapping
EXTRACT_LABELS = {
    "First Name": "first_name",
    "Middle Name": "middle_initial",
    "Last Name": "last_name",
    "Gender": "gender",
    "Birthday": "dob",
    "Address 1": "address",
    "Address 2": "address_2",
    "City": "city",
    "State": "state",
    "Zipcode": "zip",
    "Mobile Phone": "phone",
    "Email": "email",
    "Emergency Contact": "emergency_contact",
    "Contact Relation": "emergency_relation",
    "Emergency Phone": "emergency_phone",
    "Occupation": "occupation",
    "Height": "height_raw",
    "Weight": "weight_raw",
    "Target Weight": "target_weight_raw",
    "Please list any allergies": "allergies_raw",
    "Please list any medications you are currently taking including vitamins and dietary supplements": "medications_raw",
    "Please list any surgeries you have had": "surgeries_raw",
}


def extract_text_from_pdf(pdf_path):
    """Extract all text from a PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text


def parse_label_value_pairs(text):
    """Parse label/value pairs from the consult form text.

    The PDF text comes out as lines where known labels appear,
    and the very next non-empty, non-label line is the value.
    If the next non-empty line is itself a known label, the field is empty.
    """
    lines = [l.strip() for l in text.split("\n")]
    data = {}

    i = 0
    while i < len(lines):
        line = lines[i]

        if line in EXTRACT_LABELS:
            key = EXTRACT_LABELS[line]
            # Look at the next non-empty line
            j = i + 1
            value = ""
            while j < len(lines):
                candidate = lines[j]
                if candidate == "" or candidate == " ":
                    j += 1
                    continue
                if candidate == "-":
                    # Dash means empty field
                    j += 1
                    continue
                # If the candidate is a known label, this field has no value
                if candidate in KNOWN_LABELS:
                    break
                # Otherwise this is the value
                value = candidate
                break

            if value:
                data[key] = value
            i = j if j > i else i + 1
        else:
            i += 1

    return data


def parse_height(raw):
    """Parse height string. Handles both metric and imperial.

    Examples:
        '156 cm' → height_cm=156, height="5' 2\""
        "5'7\""  → height="5' 7\""
        '67 in'  → height="5' 7\""
    """
    result = {}
    raw = raw.strip()

    # Check for metric (cm)
    cm_match = re.match(r"([\d.]+)\s*cm", raw, re.IGNORECASE)
    if cm_match:
        cm = float(cm_match.group(1))
        result["height_cm"] = cm
        total_inches = cm / 2.54
        feet = int(total_inches // 12)
        inches = round(total_inches % 12)
        if inches == 12:
            feet += 1
            inches = 0
        result["height"] = f"{feet}' {inches}\""
        return result

    # Check for feet/inches format
    ft_match = re.match(r"(\d+)['\u2019]\s*(\d+)", raw)
    if ft_match:
        result["height"] = f"{ft_match.group(1)}' {ft_match.group(2)}\""
        return result

    # Check for inches only
    in_match = re.match(r"([\d.]+)\s*in", raw, re.IGNORECASE)
    if in_match:
        total = float(in_match.group(1))
        feet = int(total // 12)
        inches = round(total % 12)
        result["height"] = f"{feet}' {inches}\""
        return result

    # Pass through as-is
    result["height"] = raw
    return result


def parse_weight(raw, key_prefix="weight"):
    """Parse weight string. Handles metric (kg) and imperial (lbs).

    Examples:
        '70kg'    → weight_kg=70.0, weight='154.3 lbs'
        '154 lbs' → weight='154 lbs'
        '70 kg'   → weight_kg=70.0, weight='154.3 lbs'
    """
    result = {}
    raw = raw.strip()

    # Check for kg
    kg_match = re.match(r"([\d.]+)\s*kg", raw, re.IGNORECASE)
    if kg_match:
        kg = float(kg_match.group(1))
        result[f"{key_prefix}_kg"] = kg
        lbs = round(kg * 2.20462, 1)
        result[key_prefix] = f"{lbs} lbs"
        return result

    # Check for lbs
    lbs_match = re.match(r"([\d.]+)\s*(lbs?|pounds?)", raw, re.IGNORECASE)
    if lbs_match:
        result[key_prefix] = f"{lbs_match.group(1)} lbs"
        return result

    # Just a number — assume lbs
    num_match = re.match(r"([\d.]+)", raw)
    if num_match:
        result[key_prefix] = f"{num_match.group(1)} lbs"
        return result

    result[key_prefix] = raw
    return result


def extract_patient_data(pdf_path):
    """Main extraction function. Returns a patient data dict."""
    text = extract_text_from_pdf(pdf_path)

    # Parse label/value pairs
    raw = parse_label_value_pairs(text)

    # Build patient dict
    patient = {}

    # Direct string mappings
    simple_keys = [
        "first_name", "middle_initial", "last_name", "gender", "dob",
        "address", "city", "state", "zip", "phone", "email",
        "occupation", "emergency_contact", "emergency_relation", "emergency_phone"
    ]
    for key in simple_keys:
        if key in raw:
            patient[key] = raw[key]

    # Parse height (handles metric/imperial)
    if "height_raw" in raw:
        patient.update(parse_height(raw["height_raw"]))

    # Parse weight (handles metric/imperial)
    if "weight_raw" in raw:
        patient.update(parse_weight(raw["weight_raw"], "weight"))

    # Parse target weight
    if "target_weight_raw" in raw:
        patient.update(parse_weight(raw["target_weight_raw"], "target_weight"))

    # Medical history fields (default to standard values if empty)
    if "allergies_raw" in raw:
        patient["allergies"] = raw["allergies_raw"]
    else:
        patient["allergies"] = "NKA"

    if "medications_raw" in raw:
        patient["current_medications"] = raw["medications_raw"]
    else:
        patient["current_medications"] = "None listed"

    if "surgeries_raw" in raw:
        patient["surgeries_list"] = raw["surgeries_raw"]
    else:
        patient["surgeries_list"] = "None listed"

    return patient


def main():
    parser = argparse.ArgumentParser(description="Extract patient data from a Breakthrough Medical consult PDF")
    parser.add_argument("input_pdf", help="Path to the source consult PDF")
    parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)", default=None)
    args = parser.parse_args()

    patient = extract_patient_data(args.input_pdf)

    json_str = json.dumps(patient, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"Patient data extracted to: {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
