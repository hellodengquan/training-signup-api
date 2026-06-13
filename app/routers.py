from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import schemas, services

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/", response_model=List[schemas.Course])
def list_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return services.get_courses(db, skip=skip, limit=limit)


@router.get("/{course_id}", response_model=schemas.Course)
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = services.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/", response_model=schemas.Course, status_code=201)
def create_course(course: schemas.CourseCreate, db: Session = Depends(get_db)):
    return services.create_course(db, course)


@router.put("/{course_id}", response_model=schemas.Course)
def update_course(course_id: int, course: schemas.CourseUpdate, db: Session = Depends(get_db)):
    updated = services.update_course(db, course_id, course)
    if not updated:
        raise HTTPException(status_code=404, detail="Course not found")
    return updated


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    if not services.delete_course(db, course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return None


@router.post("/{course_id}/enroll", response_model=schemas.EnrollmentResult)
def enroll(course_id: int, enrollment: schemas.EnrollmentCreate, db: Session = Depends(get_db)):
    result = services.enroll_user(db, course_id, enrollment)
    if not result.success and result.message == "Course not found":
        raise HTTPException(status_code=404, detail=result.message)
    return result


@router.delete("/{course_id}/enrollments/{enrollment_id}", status_code=204)
def cancel_enrollment(course_id: int, enrollment_id: int, db: Session = Depends(get_db)):
    if not services.cancel_enrollment(db, course_id, enrollment_id):
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return None


@router.delete("/{course_id}/waitlist/{waitlist_id}", status_code=204)
def cancel_waitlist(course_id: int, waitlist_id: int, db: Session = Depends(get_db)):
    if not services.cancel_waitlist_entry(db, course_id, waitlist_id):
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return None


@router.get("/{course_id}/waitlist-metrics", response_model=schemas.WaitlistMetrics)
def get_waitlist_metrics(course_id: int, days: int = 7, db: Session = Depends(get_db)):
    if days > 90:
        raise HTTPException(status_code=400, detail="Maximum allowed days is 90")
    metrics = services.get_waitlist_metrics(db, course_id, days=days)
    if metrics is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return metrics
