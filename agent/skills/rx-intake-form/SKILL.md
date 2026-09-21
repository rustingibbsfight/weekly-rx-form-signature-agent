---
description: >
  Generate a fillable Patient Intake & Prescription Order Form PDF for Breakthrough
  Medical Weight Loss from a consult form PDF (or from patient data provided directly).
  Load this whenever asked to process the week's Rx forms, create a patient intake form,
  or turn a Weight Loss Medical Consultation PDF into a signable form. Produces a 2-page
  fillable PDF designed for Adobe Sign with two signer roles (Clinic Director and Physician).
---

# Breakthrough Medical — Patient Intake & Prescription Form Generator

This skill turns a consult PDF into a professional, fillable 2-page AcroForm PDF ready for Adobe Sign (signer1 = Clinic Director, signer2 = Physician).

## Locating the skill files

The scripts and logo ship with this skill package. In the sandbox, resolve the skill directory first:

```bash
SKILL_DIR="$HOME/.agents/skills/rx-intake-form"
[ -d "$SKILL_DIR" ] || SKILL_DIR="/workspace/skills/rx-intake-form"
```

Python dependencies (`reportlab`, `pypdf`, `PyMuPDF`) are pre-installed by the sandbox bootstrap. If an import fails anyway:

```bash
python3 -m pip install --break-system-packages reportlab pypdf PyMuPDF || python3 -m pip install reportlab pypdf PyMuPDF
```

## Workflow A: from a consult PDF (primary)

The source PDF (e.g. a Breakthrough Medical "Weight Loss Medical Consultation" form) should already be in the sandbox — use the `drive_download_file` tool to fetch it from Drive, e.g. to `incoming/<name>.pdf`.

### Step 1 — extract patient data

```bash
python3 "$SKILL_DIR/scripts/extract_patient_data.py" incoming/<source>.pdf -o work/patient_data.json
```

This parses label/value pairs (name, DOB, address, vitals, medications, allergies…), auto-converts metric→imperial (cm→ft/in, kg→lbs), and defaults empty medical fields ("NKA" for allergies, "None listed" for medications/surgeries).

### Step 2 — review the extracted JSON

`cat work/patient_data.json` and sanity-check it. Watch for: missing first/last name or DOB, values that are obviously another field's label, or units that look wrong. Fix the JSON in place if needed. Never fabricate values — leave unknown fields out so they stay blank on the form.

### Step 3 — generate the form

```bash
python3 "$SKILL_DIR/scripts/generate_intake_form.py" \
  work/patient_data.json \
  "out/Patient_Intake_Prescription_Form_<First>_<Last>.pdf" \
  --logo "$SKILL_DIR/assets/breakthrough_logo.png"
```

### Step 4 — deliver

Upload the generated PDF back to the week's Drive folder with the `drive_upload_file` tool, keeping the `Patient_Intake_Prescription_Form_<First>_<Last>.pdf` name.

## Workflow B: from data provided in conversation (fallback)

If there is no source PDF, gather the fields below into a JSON file and run Step 3. Commonly provided keys: `first_name`, `last_name`, `dob` (MM/DD/YYYY), `phone`, plus optional `middle_initial`, `gender`, `address`, `city`, `state`, `zip`, `email`, `occupation`, `emergency_contact`/`emergency_relation`/`emergency_phone`, `height` (imperial, `5' 7"`) or `height_cm`, `weight` (`154.3 lbs`) or `weight_kg`, `target_weight` or `target_weight_kg`, `bmi` (auto-calculated when height+weight present), `bp`, `pulse`, `current_medications`, `allergies`, `previous_rx_weight_loss`, `weight_gain_2yr`, `surgeries_list`. All fields are optional — anything missing is left blank for the clinic.

## What the form contains

- **Page 1 — Patient Intake** (Clinic Director / signer1): contact info, vitals (height, weight, BP, pulse, BMI, target weight), medical history, history/contraindication/exercise checkboxes, Clinic Director signature + date.
- **Page 2 — Prescription Order**: demographics header (signer1); Semaglutide dosing 0.25–2.4 mg and Tirzepatide dosing 2.5–15 mg checkboxes, B12/ondansetron orders, physician notes, physician signature + NPI + date (all signer2).

## Technical notes

- Field names carry Adobe Sign text tags: `_es_:signer1` (Clinic Director, 55 fields) and `_es_:signer2` (Physician, 21 fields).
- All fields are genuine AcroForm fields; post-processing strips the "required" flag from every field so Adobe Sign accepts partial fills.
- Unit conversion only happens when metric keys (`_cm`, `_kg`) are used; imperial values pass through untouched.
