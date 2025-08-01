import json
import os
import pdfkit
from jinja2 import Environment, FileSystemLoader
from collections import defaultdict

# Load student and subject data
with open('students.json') as f:
    students = json.load(f)

with open('subjects.json') as f:
    subjects_raw = json.load(f)

# Group subjects by semester
subjects_by_sem = defaultdict(list)
for code, info in subjects_raw.items():
    sem = info.get("semester", 1)  # fallback to sem 1
    subjects_by_sem[sem].append({
        "code": code,
        "name": info["name"]
    })

# Setup Jinja2
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('dummy-pdf-template.html')

# wkhtmltopdf config
config = pdfkit.configuration(
    wkhtmltopdf=r"D:\Downloads\wkhtmltox-0.12.6-1.mxe-cross-win64\wkhtmltox\bin\wkhtmltopdf.exe"
)

# Base results directory (existing structure)
results_dir = 'results'

missing_count = 0
for reg_no, student in students.items():
    student_dir = os.path.join(results_dir, reg_no)
    os.makedirs(student_dir, exist_ok=True)

    for sem, subject_list in subjects_by_sem.items():
        output_path = os.path.join(student_dir, f"{reg_no}_sem{sem}.pdf")
        if not os.path.exists(output_path):
            html_out = template.render(
                reg_no=reg_no,
                name=student["name"],
                dob=student["dob"],
                subjects=subject_list,
                semester=sem
            )
            pdfkit.from_string(html_out, output_path, configuration=config)
            print(f"📝 Generated missing PDF: {output_path}")
            missing_count += 1
        else:
            print(f"✅ Already exists: {output_path}")

print(f"\n🎉 Done. {missing_count} missing PDFs were generated.")
