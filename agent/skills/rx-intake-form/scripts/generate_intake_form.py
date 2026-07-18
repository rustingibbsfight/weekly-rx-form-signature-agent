#!/usr/bin/env python3
"""
Generate a fillable Patient Intake & Prescription Order Form for Breakthrough Medical.

Uses AcroForm fields with Adobe Sign text tag naming for two signers:
  Signer 1 (signer1) = Clinic Director — all intake fields, vitals, history, clinic signature
  Signer 2 (signer2) = Physician — medication doses, other/notes, physician signature/NPI/date

No fields are required.

Usage:
    python generate_intake_form.py <patient_json> <output_pdf> [--logo <logo_path>]

The patient JSON file should contain patient data. See SKILL.md for the schema.
"""

import argparse
import json
import math
import os
import sys

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# Post-processing imports
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NumberObject, NameObject, BooleanObject

WIDTH, HEIGHT = letter
LEFT = 0.75 * inch
RIGHT = WIDTH - 0.75 * inch
CONTENT_W = RIGHT - LEFT

# Signer prefixes for Adobe Sign text tag naming
S1 = "_es_:signer1"   # Clinic Director
S2 = "_es_:signer2"   # Physician


# ─── Unit conversion helpers ────────────────────────────────────────

def cm_to_imperial(cm):
    """Convert cm to feet and inches string like 5' 7\"."""
    total_inches = cm / 2.54
    feet = int(total_inches // 12)
    inches = round(total_inches % 12)
    if inches == 12:
        feet += 1
        inches = 0
    return f"{feet}' {inches}\""

def kg_to_lbs(kg):
    """Convert kg to lbs, rounded to 1 decimal."""
    return round(kg * 2.20462, 1)

def calculate_bmi(weight_lbs, height_inches):
    """Calculate BMI from weight in lbs and height in inches."""
    if height_inches <= 0:
        return 0
    return round(703 * weight_lbs / (height_inches ** 2), 1)

def parse_height_inches(height_str):
    """Parse a height string like '5\\' 1\"' into total inches."""
    import re
    m = re.match(r"(\d+)'\s*(\d+)", height_str)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    return 0


# ─── Visual helpers ────────────────────────────────────────────────

def draw_header(c, y, logo_path, title="Patient Intake & Prescription Order Form"):
    if logo_path and os.path.exists(logo_path):
        logo_w = 180
        logo_h = logo_w * (232 / 1001)
        logo_x = (WIDTH - logo_w) / 2
        c.drawImage(logo_path, logo_x, y - logo_h + 6, width=logo_w, height=logo_h, mask='auto')
        y -= logo_h + 2
    c.setFont("Helvetica", 9)
    c.drawCentredString(WIDTH / 2, y, "2901 W Bluegrass Blvd. Suite #200-246, Lehi, UT 84043  |  (801) 921-6340")
    y -= 20
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(WIDTH / 2, y, title)
    y -= 6
    c.setStrokeColor(colors.HexColor("#00B4D8"))
    c.setLineWidth(2)
    c.line(LEFT, y, RIGHT, y)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    return y - 18


def section_title(c, y, title):
    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#006D77"))
    c.drawString(LEFT, y, title)
    tw = c.stringWidth(title, "Helvetica-Bold", 11)
    c.setStrokeColor(colors.HexColor("#006D77"))
    c.setLineWidth(1)
    c.line(LEFT, y - 2, LEFT + tw + 4, y - 2)
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    return y - 18


def draw_footer(c):
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawCentredString(WIDTH / 2, 0.45 * inch,
        "© Doctor's Medical Clinic Version 1.5  |  Breakthrough Medical  |  2901 W Bluegrass Blvd Ste 200-246 Lehi, Utah 84043")
    c.setFillColor(colors.black)


# ─── Form field helpers ────────────────────────────────────────────

def text_field(c, name, x, y, w, h=14, value="", font_size=9):
    c.setStrokeColor(colors.grey)
    c.line(x, y - 1, x + w, y - 1)
    c.setStrokeColor(colors.black)
    c.acroForm.textfield(
        name=name,
        x=x, y=y - 2,
        width=w, height=h,
        value=value,
        fontSize=font_size,
        fontName="Helvetica",
        borderWidth=0,
        fillColor=colors.Color(0, 0, 0, alpha=0),
        textColor=colors.HexColor("#333333"),
        forceBorder=False,
    )


def label_field(c, y, label, field_name, value="", x_start=None, line_end=None, font_size=9):
    if x_start is None:
        x_start = LEFT
    c.setFont("Helvetica", 9)
    c.drawString(x_start, y, label)
    lw = c.stringWidth(label, "Helvetica", 9)
    fx = x_start + lw + 4
    if line_end is None:
        line_end = RIGHT
    fw = line_end - fx
    if fw > 0:
        text_field(c, field_name, fx, y, fw, value=value, font_size=font_size)
    return y - 18


def cb_field(c, name, x, y, checked=False, size=8):
    c.acroForm.checkbox(
        name=name,
        x=x, y=y - 1,
        size=size,
        checked=checked,
        buttonStyle="cross",
        borderWidth=1,
        borderColor=colors.black,
        fillColor=colors.white,
        forceBorder=True,
    )


def checkbox_with_label(c, name, x, y, label, checked=False, size=8):
    cb_field(c, name, x, y, checked=checked, size=size)
    c.setFont("Helvetica", 8.5)
    c.drawString(x + size + 3, y, label)
    return x + size + 3 + c.stringWidth(label, "Helvetica", 8.5) + 14


# ─── Post-processing: strip required flags ─────────────────────────

def strip_required_flags(input_path, output_path):
    """ReportLab sets the required bit on checkboxes by default.
    This removes it so Adobe Sign doesn't enforce required fields.
    Also ensures the physician_notes field has the multiline bit set."""
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)
    if "/AcroForm" in writer._root_object:
        acro = writer._root_object["/AcroForm"]
        if "/Fields" in acro:
            for field in acro["/Fields"]:
                field_obj = field.get_object()
                if "/Ff" in field_obj:
                    ff = int(field_obj["/Ff"])
                    ff = ff & ~2  # clear required bit
                    field_obj[NameObject("/Ff")] = NumberObject(ff)
                # Ensure multiline bit (bit 13 = 4096) on physician_notes
                field_name = str(field_obj.get("/T", ""))
                if "physician_notes" in field_name:
                    ff = int(field_obj.get("/Ff", 0))
                    ff = (ff & ~2) | 4096  # clear required, set multiline
                    field_obj[NameObject("/Ff")] = NumberObject(ff)
                    # Remove the cached appearance stream so the PDF viewer
                    # regenerates it with proper multiline text wrapping
                    if "/AP" in field_obj:
                        del field_obj["/AP"]
    # Also check annotations on each page for the notes widget
    for page in writer.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:
                annot_obj = annot.get_object()
                t = str(annot_obj.get("/T", ""))
                if "physician_notes" in t:
                    if "/AP" in annot_obj:
                        del annot_obj["/AP"]
                    # Remove the 100-char limit that ReportLab sets by default
                    if "/MaxLen" in annot_obj:
                        del annot_obj["/MaxLen"]
                    # Ensure multiline flag on the annotation too
                    ff = int(annot_obj.get("/Ff", 0))
                    ff = (ff & ~2) | 4096
                    annot_obj[NameObject("/Ff")] = NumberObject(ff)
    # Tell PDF viewers to regenerate all field appearances from scratch
    # This forces them to respect the multiline flag instead of using
    # ReportLab's cached single-line appearance streams
    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
    writer.write(output_path)


# ─── Main form builder ────────────────────────────────────────────

def build_form(patient, output_path, logo_path=None):
    """Build the fillable PDF from patient data dict."""

    # Extract patient fields with defaults
    first = patient.get("first_name", "")
    mi = patient.get("middle_initial", "")
    last = patient.get("last_name", "")
    gender = patient.get("gender", "")
    dob = patient.get("dob", "")
    address = patient.get("address", "")
    city = patient.get("city", "")
    state = patient.get("state", "")
    zipcode = patient.get("zip", "")
    phone = patient.get("phone", "")
    email = patient.get("email", "")
    occupation = patient.get("occupation", "")
    emergency_contact = patient.get("emergency_contact", "")
    emergency_relation = patient.get("emergency_relation", "")
    emergency_phone = patient.get("emergency_phone", "")

    # Vitals — accept metric or imperial
    height_cm = patient.get("height_cm")
    weight_kg = patient.get("weight_kg")
    target_weight_kg = patient.get("target_weight_kg")

    # If imperial provided directly, use those
    height_str = patient.get("height", "")
    weight_str = patient.get("weight", "")
    target_wt_str = patient.get("target_weight", "")
    bmi_str = patient.get("bmi", "")

    # Convert metric → imperial if metric was given
    if height_cm and not height_str:
        height_str = cm_to_imperial(float(height_cm))
    if weight_kg and not weight_str:
        lbs = kg_to_lbs(float(weight_kg))
        weight_str = f"{lbs} lbs"
    if target_weight_kg and not target_wt_str:
        lbs = kg_to_lbs(float(target_weight_kg))
        target_wt_str = f"{lbs} lbs"

    # Auto-calculate BMI if not provided
    if not bmi_str and height_str and weight_str:
        h_in = parse_height_inches(height_str)
        import re
        wt_match = re.search(r"([\d.]+)", weight_str)
        if h_in > 0 and wt_match:
            w_lbs = float(wt_match.group(1))
            bmi_str = str(calculate_bmi(w_lbs, h_in))

    bp = patient.get("bp", "")
    pulse = patient.get("pulse", "")

    # Medical history
    current_meds = patient.get("current_medications", "None listed")
    allergies = patient.get("allergies", "NKA")
    prev_rx = patient.get("previous_rx_weight_loss", "None listed")
    weight_gain = patient.get("weight_gain_2yr", "")
    surgeries_list = patient.get("surgeries_list", "None listed")

    # Full name for Rx page
    full_name = f"{first}"
    if mi:
        full_name += f" {mi}."
    if last:
        full_name += f" {last}"
    full_address = address
    if city:
        full_address += f", {city}"
    if state:
        full_address += f", {state}"
    if zipcode:
        full_address += f" {zipcode}"

    # ── Build PDF ──
    # Write to a temp path first, then post-process
    import tempfile
    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(temp_fd)

    c = canvas.Canvas(temp_path, pagesize=letter)
    c.setTitle(f"Patient Intake & Prescription Order Form - {full_name}")
    mid = LEFT + CONTENT_W * 0.52

    # ══════════════════════════════════════════════════════════════
    # PAGE 1: PATIENT INTAKE  (all fields → Signer 1: Clinic Director)
    # ══════════════════════════════════════════════════════════════
    y = HEIGHT - 0.6 * inch
    y = draw_header(c, y, logo_path)

    # ── Client Contact Information ──
    y = section_title(c, y, "Client Contact Information")

    y = label_field(c, y, "First Name: ", f"first_name{S1}", first,
                    x_start=LEFT, line_end=LEFT + CONTENT_W * 0.30)
    y += 18
    y = label_field(c, y, "MI: ", f"middle_initial{S1}", mi,
                    x_start=LEFT + CONTENT_W * 0.32, line_end=LEFT + CONTENT_W * 0.42)
    y += 18
    y = label_field(c, y, "Last Name: ", f"last_name{S1}", last,
                    x_start=LEFT + CONTENT_W * 0.44, line_end=RIGHT)

    y = label_field(c, y, "Gender: ", f"gender{S1}", gender,
                    x_start=LEFT, line_end=mid - 20)
    y += 18
    y = label_field(c, y, "Date of Birth: ", f"dob{S1}", dob,
                    x_start=mid, line_end=RIGHT)

    y = label_field(c, y, "Address: ", f"address{S1}", address,
                    x_start=LEFT, line_end=RIGHT)
    y = label_field(c, y, "City: ", f"city{S1}", city,
                    x_start=LEFT, line_end=LEFT + CONTENT_W * 0.40)
    y += 18
    y = label_field(c, y, "State: ", f"state{S1}", state,
                    x_start=LEFT + CONTENT_W * 0.42, line_end=LEFT + CONTENT_W * 0.58)
    y += 18
    y = label_field(c, y, "Zip: ", f"zip{S1}", zipcode,
                    x_start=LEFT + CONTENT_W * 0.60, line_end=RIGHT)

    y = label_field(c, y, "Mobile Phone: ", f"phone{S1}", phone,
                    x_start=LEFT, line_end=mid - 20)
    y += 18
    y = label_field(c, y, "Email: ", f"email{S1}", email,
                    x_start=mid, line_end=RIGHT)

    y = label_field(c, y, "Occupation: ", f"occupation{S1}", occupation,
                    x_start=LEFT, line_end=RIGHT)

    y = label_field(c, y, "Emergency Contact: ", f"emergency_contact{S1}", emergency_contact,
                    x_start=LEFT, line_end=LEFT + CONTENT_W * 0.55)
    y += 18
    y = label_field(c, y, "Relation: ", f"emergency_relation{S1}", emergency_relation,
                    x_start=LEFT + CONTENT_W * 0.57, line_end=RIGHT)
    y = label_field(c, y, "Emergency Phone: ", f"emergency_phone{S1}", emergency_phone,
                    x_start=LEFT, line_end=mid - 20)

    # ── Vitals ──
    y = section_title(c, y, "Vitals")
    col_w = CONTENT_W / 6
    vitals_data = [
        ("Height: ",    f"height{S1}",    height_str),
        ("Weight: ",    f"weight{S1}",    weight_str),
        ("BP:  /",      f"bp{S1}",        bp),
        ("Pulse: ",     f"pulse{S1}",     pulse),
        ("BMI: ",       f"bmi{S1}",       bmi_str),
        ("Target Wt: ", f"target_wt{S1}", target_wt_str),
    ]
    for i, (lbl, fname, val) in enumerate(vitals_data):
        x = LEFT + i * col_w
        end = x + col_w - 6
        c.setFont("Helvetica", 9)
        c.drawString(x, y, lbl)
        lw = c.stringWidth(lbl, "Helvetica", 9)
        fx = x + lw + 4
        fw = end - fx
        if fw > 0:
            text_field(c, fname, fx, y, fw, value=val)
    y -= 18

    # ── Medical History ──
    y = section_title(c, y, "Medical History")
    y = label_field(c, y, "Review of Current Medications: ", f"current_meds{S1}", current_meds,
                    x_start=LEFT, line_end=RIGHT)
    c.setStrokeColor(colors.grey)
    c.line(LEFT, y - 1, RIGHT, y - 1)
    c.setStrokeColor(colors.black)
    text_field(c, f"current_meds_2{S1}", LEFT, y, CONTENT_W)
    y -= 18

    y = label_field(c, y, "Med Allergies: ", f"allergies{S1}", allergies,
                    x_start=LEFT, line_end=RIGHT)
    y = label_field(c, y, "Previous Rx Weight Loss Medication: ", f"prev_rx{S1}", prev_rx,
                    x_start=LEFT, line_end=RIGHT)
    y = label_field(c, y, "How much weight gained in past 2 years? ", f"weight_gain_2yr{S1}", weight_gain,
                    x_start=LEFT, line_end=LEFT + CONTENT_W * 0.65)

    c.setFont("Helvetica", 9)
    c.drawString(LEFT, y, "Weight issues as a child?")
    x = LEFT + c.stringWidth("Weight issues as a child?", "Helvetica", 9) + 10
    x = checkbox_with_label(c, f"weight_child_yes{S1}", x, y, "Yes")
    checkbox_with_label(c, f"weight_child_no{S1}", x, y, "No")
    y -= 18

    # ── History ──
    y = section_title(c, y, "History")
    col1 = LEFT
    col2 = LEFT + CONTENT_W * 0.35
    col3 = LEFT + CONTENT_W * 0.65

    c.setFont("Helvetica-Bold", 9)
    c.drawString(col1, y, "Past Medical History")
    c.drawString(col2, y, "Family History")
    c.drawString(col3, y, "Past Surgical History")
    y -= 14

    pmh = ["PCOS", "Diabetes", "HTN", "Hypercholesterolemia", "Childhood Obesity"]
    fh  = ["Obesity", "Heart Disease", "Diabetes", "PCOS", ""]
    psh = ["Gastric Bypass", "Gastric Band", "Other non-Ortho Surgeries", "", ""]

    for i in range(5):
        if pmh[i]:
            checkbox_with_label(c, f"pmh_{pmh[i].lower().replace(' ','_')}{S1}", col1, y, pmh[i])
        if i < len(fh) and fh[i]:
            checkbox_with_label(c, f"fh_{fh[i].lower().replace(' ','_')}{S1}", col2, y, fh[i])
        if i < len(psh) and psh[i]:
            checkbox_with_label(c, f"psh_{psh[i].lower().replace(' ','_').replace('-','_')}{S1}", col3, y, psh[i])
        y -= 14

    y -= 2
    y = label_field(c, y, "List surgeries: ", f"list_surgeries{S1}", surgeries_list,
                    x_start=LEFT, line_end=RIGHT)

    # ── Contraindications / Exercise ──
    y -= 4
    c.setFont("Helvetica-Bold", 9)
    c.drawString(col1, y, "Contraindications")
    c.drawString(col2 + 30, y, "Exercise Level")
    y -= 14

    contras  = ["Hx of any Thyroid Cancer", "Hx of Multiple Neoplasia 1 or 2",
                "Hx Pancreatitis", "Current or Planned Pregnancy"]
    exercise = ["Sedentary", "Moderate", "Active", ""]

    for i in range(4):
        checkbox_with_label(c, f"contra_{i}{S1}", col1, y, contras[i])
        if exercise[i]:
            checkbox_with_label(c, f"exercise_{exercise[i].lower()}{S1}", col2 + 30, y, exercise[i])
        y -= 14

    # ── Clinic Director Signature ──
    y -= 14
    c.setFont("Helvetica", 9)
    c.drawString(LEFT, y, "Clinic Director Signature:")
    sig_x = LEFT + c.stringWidth("Clinic Director Signature: ", "Helvetica", 9) + 4
    sig_w = LEFT + CONTENT_W * 0.60 - sig_x
    c.setStrokeColor(colors.grey)
    c.line(sig_x, y - 1, sig_x + sig_w, y - 1)
    c.setStrokeColor(colors.black)
    c.acroForm.textfield(
        name=f"ClinicDirectorSignature{S1}:signature",
        x=sig_x, y=y - 4,
        width=sig_w, height=16,
        value="",
        fontSize=10,
        borderWidth=0,
        fillColor=colors.Color(0, 0, 0, alpha=0),
        forceBorder=False,
    )

    date_x = LEFT + CONTENT_W * 0.65
    c.drawString(date_x, y, "Date:")
    dx = date_x + c.stringWidth("Date: ", "Helvetica", 9) + 4
    dw = RIGHT - dx
    text_field(c, f"clinic_sig_date{S1}", dx, y, dw)

    draw_footer(c)
    c.showPage()

    # ══════════════════════════════════════════════════════════════
    # PAGE 2: PRESCRIPTION ORDER FORM
    # ══════════════════════════════════════════════════════════════
    y = HEIGHT - 0.6 * inch
    y = draw_header(c, y, logo_path, title="Prescription Order Form")
    y -= 6

    # Patient info (Clinic Director fills these)
    y = label_field(c, y, "Patient Name: ", f"rx_patient_name{S1}", full_name.strip(),
                    x_start=LEFT, line_end=LEFT + CONTENT_W * 0.60)
    y += 18
    y = label_field(c, y, "DOB: ", f"rx_dob{S1}", dob,
                    x_start=LEFT + CONTENT_W * 0.63, line_end=RIGHT)
    y = label_field(c, y, "Address: ", f"rx_address{S1}", full_address.strip(),
                    x_start=LEFT, line_end=RIGHT)
    y = label_field(c, y, "Phone: ", f"rx_phone{S1}", phone,
                    x_start=LEFT, line_end=mid - 20)
    y += 18
    y = label_field(c, y, "Allergies: ", f"rx_allergies{S1}", allergies,
                    x_start=mid, line_end=RIGHT)

    # ── Semaglutide ── (Physician)
    y -= 8
    y = section_title(c, y, "Semaglutide")
    c.setFont("Helvetica", 9)
    c.drawString(LEFT, y, "Initial dose (check one):")
    doses_s = ["0.25 mg", "0.5 mg", "1 mg", "1.7 mg", "2.4 mg"]
    sx = LEFT + c.stringWidth("Initial dose (check one):  ", "Helvetica", 9) + 4
    for d in doses_s:
        sx = checkbox_with_label(c, f"sema_{d.replace(' ','_').replace('.','_')}{S2}", sx, y, d)
    y -= 22
    y = label_field(c, y, "Sig: Titrate up as directed    Other: ", f"sema_other{S2}", "",
                    x_start=LEFT, line_end=RIGHT)

    # ── Tirzepatide ── (Physician)
    y -= 8
    y = section_title(c, y, "Tirzepatide")
    c.setFont("Helvetica", 9)
    c.drawString(LEFT, y, "Initial dose (check one):")
    doses_t = ["2.5 mg", "5 mg", "7.5 mg", "10 mg", "12.5 mg", "15 mg"]
    sx = LEFT + c.stringWidth("Initial dose (check one):  ", "Helvetica", 9) + 4
    for d in doses_t:
        sx = checkbox_with_label(c, f"tirz_{d.replace(' ','_').replace('.','_')}{S2}", sx, y, d)
    y -= 22
    y = label_field(c, y, "Sig: Titrate up as directed    Other: ", f"tirz_other{S2}", "",
                    x_start=LEFT, line_end=RIGHT)

    # ── Additional Orders ── (Physician)
    y = section_title(c, y, "Additional Orders")
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(LEFT, y, "B12 shot approved:")
    bx = LEFT + c.stringWidth("B12 shot approved:  ", "Helvetica-Bold", 9.5) + 6
    bx = checkbox_with_label(c, f"b12_yes{S2}", bx, y, "Yes")
    checkbox_with_label(c, f"b12_no{S2}", bx, y, "No")
    y -= 22

    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(LEFT, y, "Standing order for ondansetron 4mg ODT #20 as needed:")
    bx = LEFT + c.stringWidth("Standing order for ondansetron 4mg ODT #20 as needed:  ", "Helvetica-Bold", 9.5) + 6
    bx = checkbox_with_label(c, f"ondansetron_yes{S2}", bx, y, "Yes")
    checkbox_with_label(c, f"ondansetron_no{S2}", bx, y, "No")
    y -= 30

    # ── Physician Notes ── (Physician)
    y = section_title(c, y, "Physician Notes")
    notes_height = 120
    c.setStrokeColor(colors.grey)
    c.rect(LEFT, y - notes_height, CONTENT_W, notes_height + 4, stroke=1, fill=0)
    c.setStrokeColor(colors.black)
    c.acroForm.textfield(
        name=f"physician_notes{S2}",
        x=LEFT + 2, y=y - notes_height + 2,
        width=CONTENT_W - 4, height=notes_height,
        value="",
        fontSize=9,
        fontName="Helvetica",
        borderWidth=0,
        fillColor=colors.Color(0, 0, 0, alpha=0),
        textColor=colors.HexColor("#333333"),
        forceBorder=False,
        fieldFlags="multiline",
    )
    y -= notes_height + 12

    # ── Physician Signature ── (Signer 2)
    y -= 12
    c.setFont("Helvetica", 9)

    c.drawString(LEFT, y, "Physician Signature:")
    psig_x = LEFT + c.stringWidth("Physician Signature: ", "Helvetica", 9) + 4
    psig_w = LEFT + CONTENT_W * 0.50 - psig_x
    c.setStrokeColor(colors.grey)
    c.line(psig_x, y - 1, psig_x + psig_w, y - 1)
    c.setStrokeColor(colors.black)
    c.acroForm.textfield(
        name=f"PhysicianSignature{S2}:signature",
        x=psig_x, y=y - 4,
        width=psig_w, height=16,
        value="",
        fontSize=10,
        borderWidth=0,
        fillColor=colors.Color(0, 0, 0, alpha=0),
        forceBorder=False,
    )

    npi_label_x = LEFT + CONTENT_W * 0.53
    c.drawString(npi_label_x, y, "NPI:")
    npi_x = npi_label_x + c.stringWidth("NPI: ", "Helvetica", 9) + 4
    npi_w = LEFT + CONTENT_W * 0.75 - npi_x
    text_field(c, f"npi{S2}", npi_x, y, npi_w)

    date_label_x = LEFT + CONTENT_W * 0.78
    c.drawString(date_label_x, y, "Date:")
    rx_dx = date_label_x + c.stringWidth("Date: ", "Helvetica", 9) + 4
    rx_dw = RIGHT - rx_dx
    text_field(c, f"rx_sig_date{S2}", rx_dx, y, rx_dw)

    draw_footer(c)
    c.save()

    # Post-process: strip required flags from all fields
    strip_required_flags(temp_path, output_path)

    # Clean up temp file
    os.unlink(temp_path)
    print(f"Fillable PDF created: {output_path}")


# ─── CLI entry point ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Breakthrough Medical Intake Form")
    parser.add_argument("patient_json", help="Path to patient data JSON file")
    parser.add_argument("output_pdf", help="Output PDF file path")
    parser.add_argument("--logo", help="Path to logo image (PNG)", default=None)
    args = parser.parse_args()

    with open(args.patient_json) as f:
        patient = json.load(f)

    build_form(patient, args.output_pdf, logo_path=args.logo)


if __name__ == "__main__":
    main()
