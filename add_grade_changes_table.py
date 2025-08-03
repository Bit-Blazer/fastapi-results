#!/usr/bin/env python3
"""
Database migration script to add the grade_changes table.
Run this script to add the new table for tracking grade changes.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

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

def migrate_database():
    """Add the grade_changes table to the database."""
    try:
        engine = create_engine(DATABASE_URL)
        
        # SQL to create the grade_changes table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS grade_changes (
            id SERIAL PRIMARY KEY,
            regno VARCHAR(20) NOT NULL,
            subject_code VARCHAR(20) NOT NULL,
            semester INTEGER NOT NULL,
            original_grade VARCHAR(5) NOT NULL,
            new_grade VARCHAR(5) NOT NULL,
            credits INTEGER NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT idx_grade_changes_regno_subject_semester 
                UNIQUE (regno, subject_code, semester, changed_at)
        );
        """
        
        # Create index for better query performance
        create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_grade_changes_regno 
        ON grade_changes (regno);
        
        CREATE INDEX IF NOT EXISTS idx_grade_changes_changed_at 
        ON grade_changes (changed_at);
        """
        
        with engine.connect() as connection:
            # Create the table
            connection.execute(text(create_table_sql))
            print("✅ Created grade_changes table successfully!")
            
            # Create indexes
            connection.execute(text(create_index_sql))
            print("✅ Created indexes successfully!")
            
            # Commit the transaction
            connection.commit()
            
        print("\n🎉 Migration completed successfully!")
        print("\nThe grade_changes table has been added with the following columns:")
        print("  - id (Primary Key)")
        print("  - regno (Student Registration Number)")
        print("  - subject_code (Subject Code)")
        print("  - semester (Semester Number)")
        print("  - original_grade (Original Grade)")
        print("  - new_grade (New Grade)")
        print("  - credits (Subject Credits)")
        print("  - changed_at (Timestamp of Change)")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    return True

def check_table_exists():
    """Check if the grade_changes table already exists."""
    try:
        engine = create_engine(DATABASE_URL)
        
        check_sql = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'grade_changes'
        );
        """
        
        with engine.connect() as connection:
            result = connection.execute(text(check_sql))
            exists = result.fetchone()[0]
            return exists
            
    except Exception as e:
        print(f"❌ Error checking table existence: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting grade_changes table migration...")
    
    # Check if table already exists
    if check_table_exists():
        print("ℹ️  grade_changes table already exists. Skipping migration.")
    else:
        print("📝 grade_changes table not found. Creating...")
        migrate_database()
