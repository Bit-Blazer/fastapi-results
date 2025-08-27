"""
API routes for grade changes functionality
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from .database import get_db, Student, GradeChange, StudentLoginLog

# Create router for API routes
router = APIRouter(prefix="/api")

IST = timezone(timedelta(hours=5, minutes=30))  # +05:30


def is_admin_authenticated(request: Request) -> bool:
    """Check if admin is authenticated in the session"""
    return request.session.get("admin_authenticated", False)


# Pydantic models for API requests
class GradeChangeRequest(BaseModel):
    regno: str
    subject_code: str
    semester: int
    original_grade: str
    new_grade: str
    credits: int
    timestamp: str


@router.post("/grade-changes/")
async def save_grade_change(
    grade_change: GradeChangeRequest, request: Request, db: Session = Depends(get_db)
):
    try:
        # Validate that the student exists
        student = db.query(Student).filter(Student.regno == grade_change.regno).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Create new grade change record
        grade_change_record = GradeChange(
            regno=grade_change.regno,
            subject_code=grade_change.subject_code,
            semester=grade_change.semester,
            original_grade=grade_change.original_grade,
            new_grade=grade_change.new_grade,
            credits=grade_change.credits,
            changed_at=datetime.now(IST),
        )

        # Save to database
        db.add(grade_change_record)
        db.commit()
        db.refresh(grade_change_record)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Grade change saved successfully",
                "change_id": grade_change_record.id,
                "timestamp": grade_change_record.changed_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to save grade change: {str(e)}",
            },
        )


@router.delete("/grade-changes/{change_id}")
async def delete_grade_change(
    change_id: int, request: Request, db: Session = Depends(get_db)
):
    """Delete a specific grade change by ID"""
    # Check admin authentication
    if not is_admin_authenticated(request):
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Authentication required"},
        )

    try:
        # Find the grade change record
        grade_change = db.query(GradeChange).filter(GradeChange.id == change_id).first()

        if not grade_change:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Grade change not found"},
            )

        # Delete the record
        db.delete(grade_change)
        db.commit()

        return JSONResponse(
            content={
                "success": True,
                "message": "Grade change deleted successfully",
                "deleted_id": change_id,
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to delete grade change: {str(e)}",
            },
        )


@router.get("/grade-changes/")
async def get_grade_changes(
    request: Request, db: Session = Depends(get_db), regno: str = None, limit: int = 100, offset: int = 0
):
    """Get grade changes - all students or filtered by registration number"""
    # Check admin authentication
    if not is_admin_authenticated(request):
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Authentication required"},
        )
        
    try:
        # Base query with student names
        query = db.query(GradeChange, Student.name).join(
            Student, GradeChange.regno == Student.regno
        )

        # If regno is provided, filter by it and validate student exists
        if regno:
            student = db.query(Student).filter(Student.regno == regno).first()
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            query = query.filter(GradeChange.regno == regno)

        # Apply ordering, offset and limit
        grade_changes = (
            query.order_by(GradeChange.changed_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Format the response
        changes_data = []
        for change, student_name in grade_changes:
            changes_data.append(
                {
                    "id": change.id,
                    "regno": change.regno,
                    "student_name": student_name,
                    "subject_code": change.subject_code,
                    "semester": change.semester,
                    "original_grade": change.original_grade,
                    "new_grade": change.new_grade,
                    "credits": change.credits,
                    "changed_at": change.changed_at.isoformat(),
                    "grade_difference": f"{change.original_grade} → {change.new_grade}",
                }
            )

        # Get total count (with same filter if applied)
        total_query = db.query(GradeChange)
        if regno:
            total_query = total_query.filter(GradeChange.regno == regno)
        total_changes = total_query.count()

        # Prepare response content
        response_content = {
            "success": True,
            "total_changes": total_changes,
            "showing": len(changes_data),
            "offset": offset,
            "limit": limit,
            "changes": changes_data,
        }

        # Add student info if filtering by regno
        if regno:
            response_content["filtered_by_regno"] = regno
            if changes_data:  # If we have data, we know student exists
                response_content["student_name"] = changes_data[0]["student_name"]

        return JSONResponse(
            status_code=200,
            content=response_content,
        )

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to retrieve grade changes: {str(e)}",
            },
        )


@router.get("/student-logs")
async def student_logs_data(request: Request, db: Session = Depends(get_db)):
    """API endpoint for student logs data"""
    if not is_admin_authenticated(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        # Get recent student login logs (last 100)
        student_logs = (
            db.query(StudentLoginLog)
            .order_by(desc(StudentLoginLog.login_time))
            .limit(100)
            .all()
        )

        # Calculate statistics
        total_logins = len(student_logs)
        unique_students = len(set(log.regno for log in student_logs))

        # Format logs for frontend
        formatted_logs = []
        for log in student_logs:

            formatted_logs.append(
                {
                    "name": log.student_name,
                    "regno": log.regno,
                    "login_time": log.login_time.isoformat(),
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                }
            )

        return JSONResponse(
            {
                "logs": formatted_logs,
                "stats": {
                    "total_logins": total_logins,
                    "unique_students": unique_students,
                },
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
