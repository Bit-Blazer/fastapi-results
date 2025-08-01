import os
import json
import re
from pathlib import Path
from PyPDF2 import PdfReader

# --- Config ---
PDF_FOLDER = "res"  # Folder containing result PDFs
OUTPUT_JSON = "subjects.json"  # Output file
DEFAULT_CREDITS = 0  # Default value for credits

# --- Regex Pattern ---
subject_regex = re.compile(
    r"(2[123][A-Z]{2,3}\d{2,3}[TL])\s*(?:-\s|\s)([A-Za-z,\s]+)\s(A\+?|B\+?|C|O|U|AB)\s(\d*)\s(\d)\b"
)


# --- Extract subjects from a single PDF ---
def extract_subjects_from_pdf(pdf_path):
    subjects = {}
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        # print(full_text)
        #      return
        for match in subject_regex.finditer(full_text):
            code = match.group(1).strip()
            name = match.group(2).strip()
            cred = match.group(5).strip()
            if code not in subjects:
                subjects[code] = {"name": name, "credits": cred}

    except Exception as e:
        print(f"[ERROR] Failed to read {pdf_path}: {e}")
    return subjects


# --- Main function ---
def generate_subjects_json():
    all_subjects = {}
    pdf_dir = Path(PDF_FOLDER)

    if not pdf_dir.exists():
        print(f"[ERROR] Folder '{PDF_FOLDER}' not found.")
        return

    for pdf_file in pdf_dir.glob("*.pdf"):
        print(f"[INFO] Processing: {pdf_file.name}")
        subjects = extract_subjects_from_pdf(pdf_file)
        all_subjects.update(subjects)

    with open(OUTPUT_JSON, "w") as f:
        json.dump(all_subjects, f, indent=4)

    print(
        f"\n✅ Done. Extracted {len(all_subjects)} unique subjects to '{OUTPUT_JSON}'"
    )


# --- Entry point ---
if __name__ == "__main__":
    generate_subjects_json()
