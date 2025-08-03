"""
Database Reset Script - Wipe and recreate the database from scratch
"""

from database import Base, engine, SessionLocal, Student, test_connection


def reset_database():
    """Drop all tables and recreate them"""
    print("🚨 RESETTING DATABASE - This will delete ALL data!")
    print("=" * 50)

    # Test connection first
    if not test_connection():
        print("❌ Cannot connect to database. Check your .env file.")
        return False

    try:
        # Drop all existing tables
        print("🗑️  Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        print("✅ All tables dropped successfully!")

        # Recreate all tables
        print("🔨 Creating fresh tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")

        print("\nTables recreated:")
        print("  - students")
        print("  - subjects")
        print("  - semesters")
        print("  - grades")

        return True

    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        return False


def add_sample_students():
    """Add some sample students for testing"""
    print("\n📝 Adding sample students...")

    db = SessionLocal()
    try:
        # Sample students data
        sample_students = [
            {"regno": "113222031001", "name": "John Doe", "dob": "01-01-2000"},
            {"regno": "113222031002", "name": "Jane Smith", "dob": "15-05-2000"},
            {"regno": "113222031003", "name": "Bob Johnson", "dob": "20-12-1999"},
        ]

        for student_data in sample_students:
            student = Student(
                regno=student_data["regno"],
                name=student_data["name"],
                dob=student_data["dob"],
            )
            db.add(student)

        db.commit()
        print(f"✅ Added {len(sample_students)} sample students")

        # Show added students
        print("\nSample students added:")
        for student_data in sample_students:
            print(
                f"  - {student_data['regno']}: {student_data['name']} (DOB: {student_data['dob']})"
            )

    except Exception as e:
        print(f"❌ Error adding sample students: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Main function"""
    print("Database Reset Utility")
    print("=" * 30)

    # Ask for confirmation
    confirm = input(
        "\nAre you sure you want to WIPE ALL DATABASE DATA? (type 'YES' to confirm): "
    )

    if confirm != "YES":
        print("❌ Reset cancelled.")
        return

    # Reset database
    if reset_database():
        # Ask if user wants sample data
        add_samples = (
            input("\nAdd sample students for testing? (y/n): ").lower().strip()
        )

        if add_samples in ["y", "yes"]:
            add_sample_students()

        print("\n🎉 Database reset completed!")
        print("\nNext steps:")
        print("1. Put your PDF files in the 'Results' folder")
        print("2. Run: python pdf_processor.py")
        print("3. Test the web app: python main.py")
    else:
        print("❌ Database reset failed!")


if __name__ == "__main__":
    main()
