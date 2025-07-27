import re
import json
import fitz  # PyMuPDF
from pathlib import Path

# Patterns
dob_pattern = r"D\.O\.B : (\d{2}-\d{2}-\d{4})"
name_pattern = r"Name\s: ([A-Z ]+)"
reg_pattern = r"\d{12}"

results_dir = Path("results")
output_file = Path("students.json")

students = {}

for pdf_path in results_dir.rglob("*.pdf"):
    try:
        with fitz.open(pdf_path) as doc:
            text = ""
            for page in doc:
                text += page.get_text()

            reg_match = re.search(reg_pattern, text)
            name_match = re.search(name_pattern, text)
            dob_match = re.search(dob_pattern, text)

            if reg_match:
                regno = reg_match.group(0)
                name = name_match.group(1).strip().title() if name_match else None
                dob = dob_match.group(1).strip() if dob_match else None

                if regno not in students:
                    students[regno] = {}

                if name:
                    students[regno]["name"] = name
                if dob:
                    students[regno]["dob"] = dob

    except Exception as e:
        print(f"Error reading {pdf_path.name}: {e}")

# Save to file
with open(output_file, "w") as f:
    json.dump(students, f, indent=2)

print(f"✅ Extracted {len(students)} students → {output_file}")
