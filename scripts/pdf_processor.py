"""
PDF Processor - Extract grades from PDFs and store in database
This processes PDFs and uploads them to Supabase Storage
"""

import re
import fitz  # PyMuPDF
from pathlib import Path
from sqlalchemy.orm import Session
import logging
from datetime import datetime
import json
from database import (
    SessionLocal,
    Student,
    Subject,
    Semester,
    Grade,
    upload_pdf,
)


class PDFProcessor:
    def __init__(self):
        # Setup logging
        self.setup_logging()

        # Load subjects data from JSON file
        self.load_subjects_data()

        # Hardcoded folder path for downloaded PDFs
        self.pdf_folder = Path(r"d:\Documents\results\results")
        self.exam_semester_map = {
            "MAY 2025": 6,
            "NOV 2024": 5,
            "MAY 2024": 4,
            "November 2023": 3,
            "JUL 23": 2,
            "MARCH 2023": 1,
            # TODO: Add more mappings as you encounter new exam dates
        }

        self.grade_points = {
            "O": 10,
            "A+": 9,
            "A": 8,
            "B+": 7,
            "B": 6,
            "C": 5,
            "U": 0,
            "RA": 0,
            "AB": 0,
            "NA": 0,
        }

        # Regex to extract 12-digit registration number
        self.reg_pattern = re.compile(r"\d{12}")

        self.subject_regex = re.compile(
            r"(\d)\s*(2[123][A-Z]{2,3}\d{2,3}[TL])\s*(?:-\s|\s)([A-Za-z,\s]+)\s(A\+?|B\+?|C|O|U|AB|NA)\s",
            re.IGNORECASE,
        )

    def setup_logging(self):
        """Setup logging to both console and file"""
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"pdf_processing_{timestamp}.log"

        # Setup logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(),  # Console output
            ],
        )

        self.logger = logging.getLogger(__name__)
        self.log_file_path = log_file

        self.log(f"🚀 PDF Processing started - Logs saved to: {log_file}")

    def load_subjects_data(self):
        """Load subjects data from JSON file"""
        try:
            subjects_file = Path("subjects.json")
            if subjects_file.exists():
                with open(subjects_file, "r", encoding="utf-8") as f:
                    self.subjects_data = json.load(f)
                self.log(
                    f"📚 Loaded {len(self.subjects_data)} subjects from subjects.json"
                )
            else:
                self.log("⚠️  subjects.json not found, using default credits")
                self.subjects_data = {}
        except Exception as e:
            self.log(f"❌ Error loading subjects.json: {e}")
            self.subjects_data = {}

    def log(self, message):
        """Log message to both console and file"""
        self.logger.info(message)

    def extract_gpa(self, text: str):
        """Extract GPA from PDF text"""
        gpa_pattern = r"=> (.*)"
        try:
            match = re.search(gpa_pattern, text)
            if match:
                return float(match.group(1).strip())
        except Exception:
            return None
        return None

    def extract_name(self, text: str):
        """Extract student name from PDF text"""
        name_pattern = r"Name\s: ([A-Za-z ]*)"
        try:
            match = re.search(name_pattern, text)
            if match:
                return match.group(1).title()
        except Exception:
            return None
        return None

    def extract_regno(self, text: str):
        """Extract 12-digit registration number from PDF text"""
        try:
            match = self.reg_pattern.search(text)
            if match:
                return match.group(0)
        except Exception:
            return None
        return None

    def extract_semester_number(self, text: str):
        """Extract semester number from exam date in PDF text"""
        try:
            # Look for exam date pattern like "Provisional Results for NOV 2024 Examinations"
            exam_date_pattern = r"Provisional Results for ([A-Za-z]* \d*) Examinations"
            match = re.search(exam_date_pattern, text, re.IGNORECASE)

            if match:
                exam_date = match.group(1)  # e.g., "NOV 2024"
                semester_num = self.exam_semester_map.get(exam_date)
                if semester_num:
                    return semester_num
                else:
                    self.log(
                        f"⚠️  Exam date '{exam_date}' not found in semester mapping"
                    )
        except Exception as e:
            self.log(f"⚠️  Error extracting semester number: {e}")
            return None
        return None

    def extract_dob(self, text: str):
        """Extract student date of birth from PDF text"""
        dob_pattern = r"D\.O\.B : (\d{2}-\d{2}-\d{4})"
        try:
            match = re.search(dob_pattern, text)
            if match:
                return match.group(1).strip()
        except Exception:
            return None
        return None

    def extract_pdf_text(self, pdf_path: Path):
        """Extract all text from PDF once"""
        try:
            with fitz.open(pdf_path) as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            self.log(f"❌ Error reading PDF {pdf_path.name}: {e}")
            return None

    def get_or_create_subject(
        self, db: Session, code: str, name: str, credits: int, semester: int
    ):
        """Get existing subject or create new one"""
        # First try to find by code
        subject = db.query(Subject).filter(Subject.code == code).first()

        if not subject:
            # Create new subject
            subject = Subject(
                code=code, name=name.strip(), credits=credits, semester=semester
            )
            db.add(subject)
            db.commit()
            db.refresh(subject)
            self.log(f"➕ Added new subject: {code} - {name}")

        return subject

    def get_subject_credits(self, subject_code: str) -> int:
        """Get credits for a subject from the loaded data, default to 4 if not found"""
        if subject_code in self.subjects_data:
            return self.subjects_data[subject_code].get("credits", 4)
        else:
            self.log(
                f"⚠️  Subject {subject_code} not found in subjects.json, using default credits (4)"
            )
            return 4

    def process_pdf(self, pdf_path: Path):
        """Process a single PDF file"""
        db = SessionLocal()
        try:
            self.log(f"📄 Processing: {pdf_path.name}")

            # Extract text once and pass to all functions
            text = self.extract_pdf_text(pdf_path)
            if not text:
                self.log(f"❌ Could not read PDF content from {pdf_path.name}")
                return

            # Extract basic info
            regno = self.extract_regno(text)
            if not regno:
                self.log(
                    f"⚠️  Could not extract registration number from {pdf_path.name}"
                )
                return

            semester_num = self.extract_semester_number(text)
            if not semester_num:
                self.log(f"⚠️  Could not extract semester number from {pdf_path.name}")
                return

            # Get or create student
            student = db.query(Student).filter(Student.regno == regno).first()
            if not student:
                name = self.extract_name(text)
                if not name:
                    self.log(f"⚠️  Could not extract student name from {pdf_path.name}")
                    return

                dob = self.extract_dob(text)
                if not dob:
                    self.log(f"⚠️  Could not extract student DOB from {pdf_path.name}")
                    return

                student = Student(regno=regno, name=name, dob=dob)
                db.add(student)
                db.commit()
                db.refresh(student)
                self.log(f"➕ Added new student: {regno} - {name} (DOB: {dob})")

            # Check if semester already processed
            existing_semester = (
                db.query(Semester)
                .filter(
                    Semester.student_id == student.id, Semester.semester == semester_num
                )
                .first()
            )

            if existing_semester:
                self.log(f"⏭️  Semester {semester_num} for {regno} already processed")
                return

            # Upload PDF to storage with new naming convention
            storage_path = f"{regno}/{regno}_sem{semester_num}.pdf"
            uploaded_path = upload_pdf(pdf_path, storage_path)

            if not uploaded_path:
                self.log(f"❌ Failed to upload {regno}_sem{semester_num}.pdf")
                # Continue processing even if upload fails

            # Extract GPA
            gpa = self.extract_gpa(text)

            # Create semester record
            semester_record = Semester(
                student_id=student.id, semester=semester_num, gpa=gpa
            )
            db.add(semester_record)
            db.commit()
            db.refresh(semester_record)

            # Extract and process grades
            grades_added = 0
            matches = self.subject_regex.findall(text)

            for match in matches:
                sub_semester, code, name, grade = match
                sub_semester = int(sub_semester)

                # Get or create subject
                credits = self.get_subject_credits(code)  # Get credits from loaded data
                subject = self.get_or_create_subject(
                    db, code, name, credits, sub_semester
                )

                # Handle arrear logic: if subject's semester doesn't match current semester,
                # update the grade in the original semester
                if sub_semester != semester_num:
                    # This is an arrear - find the original semester record
                    original_semester = (
                        db.query(Semester)
                        .filter(
                            Semester.student_id == student.id,
                            Semester.semester == sub_semester,
                        )
                        .first()
                    )

                    if original_semester:
                        # Check if grade already exists
                        existing_grade = (
                            db.query(Grade)
                            .filter(
                                Grade.semester_id == original_semester.id,
                                Grade.subject_id == subject.id,
                            )
                            .first()
                        )

                        if existing_grade:
                            # Update existing grade
                            old_grade = existing_grade.grade
                            existing_grade.grade = grade
                            existing_grade.grade_points_earned = (
                                subject.credits * self.grade_points.get(grade, 0)
                            )
                            self.log(
                                f"🔄 Updated arrear grade for {code}: {old_grade} → {grade} (Semester {sub_semester})"
                            )
                        else:
                            # Create new grade record in original semester
                            grade_points_earned = (
                                subject.credits * self.grade_points.get(grade, 0)
                            )
                            new_grade = Grade(
                                semester_id=original_semester.id,
                                subject_id=subject.id,
                                grade=grade,
                                grade_points_earned=grade_points_earned,
                            )
                            db.add(new_grade)
                            self.log(
                                f"➕ Added arrear grade for {code}: {grade} (Semester {sub_semester})"
                            )
                    else:
                        self.log(
                            f"⚠️  Original semester {sub_semester} not found for arrear subject {code}"
                        )
                else:
                    # Regular subject for current semester
                    grade_points_earned = subject.credits * self.grade_points.get(
                        grade, 0
                    )
                    new_grade = Grade(
                        semester_id=semester_record.id,
                        subject_id=subject.id,
                        grade=grade,
                        grade_points_earned=grade_points_earned,
                    )
                    db.add(new_grade)
                    grades_added += 1

            db.commit()
            self.log(f"✅ Processed: {regno} sem{semester_num} - {grades_added} grades")

        except Exception as e:
            db.rollback()
            self.log(f"❌ Error processing {pdf_path.name}: {e}")
        finally:
            db.close()

    def process_all_pdfs(self):
        """Process all PDFs in the folder"""
        self.log("🚀 Starting PDF processing...")
        self.log(f"📁 Processing PDFs from: {self.pdf_folder}")

        if not self.pdf_folder.exists():
            self.log(f"❌ PDF folder does not exist: {self.pdf_folder}")
            return

        pdf_files = list(self.pdf_folder.rglob("*.pdf"))
        if not pdf_files:
            self.log(f"⚠️  No PDF files found in {self.pdf_folder}")
            return

        self.log(f"📊 Found {len(pdf_files)} PDF files to process")

        for pdf_file in pdf_files:
            self.process_pdf(pdf_file)

        self.log("🎉 PDF processing completed!")
        self.log(f"📁 All logs saved to: {self.log_file_path}")


def main():
    processor = PDFProcessor()
    processor.process_all_pdfs()


if __name__ == "__main__":
    main()
