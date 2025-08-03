import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DECIMAL,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to constructing from individual components
    SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    SUPABASE_PORT = os.getenv("SUPABASE_PORT", "")
    DATABASE_URL = f"postgresql://postgres:{DB_PASSWORD}@db.{SUPABASE_PROJECT_ID}.supabase.co:{SUPABASE_PORT}/postgres"
STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME")

# Supabase client for storage
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    regno = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    dob = Column(String(10), nullable=False)  # Format: DD-MM-YYYY

    # Relationships
    semesters = relationship("Semester", back_populates="student")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    credits = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)  # Expected semester (1-8)

    # Relationships
    grades = relationship("Grade", back_populates="subject")


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    semester = Column(Integer, nullable=False)  # e.g., 1, 2, 3, 4, 5, 6, 7, 8
    gpa = Column(DECIMAL(4, 2))  # e.g., 8.75

    # Relationships
    student = relationship("Student", back_populates="semesters")
    grades = relationship("Grade", back_populates="semester")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    grade = Column(String(5), nullable=False)  # O, A+, A, B+, B, C, U, etc.
    grade_points_earned = Column(
        Integer, nullable=False
    )  # credits × grade_point (both integers)

    # Relationships
    semester = relationship("Semester", back_populates="grades")
    subject = relationship("Subject", back_populates="grades")


# Database functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Supabase Storage functions
def upload_pdf(file_path: Path, storage_path: str) -> str:
    """
    Upload PDF file to Supabase Storage

    Args:
        file_path: Local path to the PDF file
        storage_path: Path in storage (e.g., "113222031001/113222031001_1.pdf")

    Returns:
        Storage path of the uploaded file (for private bucket access)
    """
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        # Upload to storage
        result = supabase.storage.from_(STORAGE_BUCKET_NAME).upload(
            path=storage_path,
            file=file_data,
            file_options={"content-type": "application/pdf"},
        )

        if result:
            # Return storage path
            print(f"✅ Uploaded: {storage_path}")
            return storage_path
        else:
            print(f"❌ Upload failed: {storage_path}")
            return None

    except Exception as e:
        print(f"❌ Error uploading {storage_path}: {e}")
        return None


def download_pdf(storage_path: str) -> bytes:
    """
    Securely download PDF content for authorized access (RECOMMENDED for private buckets)

    This is the primary method for serving PDFs from private buckets.
    Use this when you need to serve PDFs through authenticated endpoints.

    Args:
        storage_path: Path in storage

    Returns:
        PDF file content as bytes, or None if not found
    """
    print(f"🔄 Downloading PDF from storage: {storage_path}")
    try:
        result = supabase.storage.from_(STORAGE_BUCKET_NAME).download(storage_path)
        return result
    except Exception as e:
        print(f"❌ Error downloading {storage_path}: {e}")
        return None


def test_connection():
    """Test database connection"""
    try:
        engine.connect()
        print("✅ Database connection successful!")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def setup_database():
    """Setup database and storage"""
    print("🚀 Setting up Supabase database...")

    # Test database connection
    if not test_connection():
        print("❌ Cannot connect to database. Check your .env file.")
        return

    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        print("\nTables created:")
        print("  - students")
        print("  - subjects")
        print("  - semesters")
        print("  - grades")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
