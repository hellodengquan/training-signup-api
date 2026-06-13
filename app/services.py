from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app import models, schemas


def get_course(db: Session, course_id: int) -> Optional[models.Course]:
    return db.query(models.Course).filter(models.Course.id == course_id).first()


def get_courses(db: Session, skip: int = 0, limit: int = 100):
    courses = db.query(models.Course).offset(skip).limit(limit).all()
    result = []
    for course in courses:
        result.append(_enrich_course_with_counts(db, course))
    return result


def create_course(db: Session, course: schemas.CourseCreate) -> models.Course:
    db_course = models.Course(**course.model_dump())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return _enrich_course_with_counts(db, db_course)


def update_course(db: Session, course_id: int, course: schemas.CourseUpdate) -> Optional[models.Course]:
    db_course = get_course(db, course_id)
    if not db_course:
        return None
    update_data = course.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_course, key, value)
    db.commit()
    db.refresh(db_course)
    return _enrich_course_with_counts(db, db_course)


def delete_course(db: Session, course_id: int) -> bool:
    db_course = get_course(db, course_id)
    if not db_course:
        return False
    db.delete(db_course)
    db.commit()
    return True


def enroll_user(db: Session, course_id: int, enrollment: schemas.EnrollmentCreate) -> schemas.EnrollmentResult:
    course = get_course(db, course_id)
    if not course:
        return schemas.EnrollmentResult(success=False, message="Course not found")

    enrolled_count = _get_enrolled_count(db, course_id)

    if enrolled_count < course.capacity:
        db_enrollment = models.Enrollment(
            course_id=course_id,
            **enrollment.model_dump()
        )
        db.add(db_enrollment)
        db.commit()
        db.refresh(db_enrollment)
        return schemas.EnrollmentResult(
            success=True,
            message="Enrollment confirmed",
            status="confirmed"
        )

    waitlist_count = _get_waiting_waitlist_count(db, course_id)
    if course.waitlist_capacity is not None and waitlist_count >= course.waitlist_capacity:
        return schemas.EnrollmentResult(
            success=False,
            message="Waitlist is full"
        )

    position = waitlist_count + 1
    db_waitlist = models.WaitlistEntry(
        course_id=course_id,
        position=position,
        **enrollment.model_dump()
    )
    db.add(db_waitlist)
    db.commit()
    db.refresh(db_waitlist)
    return schemas.EnrollmentResult(
        success=True,
        message="Added to waitlist",
        status="waitlisted",
        position=position
    )


def cancel_enrollment(db: Session, course_id: int, enrollment_id: int) -> bool:
    enrollment = db.query(models.Enrollment).filter(
        models.Enrollment.id == enrollment_id,
        models.Enrollment.course_id == course_id
    ).first()
    if not enrollment:
        return False

    db.delete(enrollment)
    db.commit()
    _promote_next_waitlist_user(db, course_id)
    return True


def cancel_waitlist_entry(db: Session, course_id: int, waitlist_id: int) -> bool:
    entry = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.id == waitlist_id,
        models.WaitlistEntry.course_id == course_id,
        models.WaitlistEntry.status == "waiting"
    ).first()
    if not entry:
        return False

    entry.status = "cancelled"
    db.commit()
    _recompute_waitlist_positions(db, course_id)
    return True


def get_waitlist_metrics(db: Session, course_id: int) -> Optional[dict]:
    course = get_course(db, course_id)
    if not course:
        return None

    current_waitlist_length = _get_waiting_waitlist_count(db, course_id)

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    promoted_entries = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.course_id == course_id,
        models.WaitlistEntry.status == "promoted",
        models.WaitlistEntry.promoted_at >= seven_days_ago
    ).all()

    avg_wait_seconds = 0.0
    if promoted_entries:
        total_wait = 0
        for entry in promoted_entries:
            if entry.joined_at and entry.promoted_at:
                wait_delta = entry.promoted_at - entry.joined_at
                total_wait += wait_delta.total_seconds()
        avg_wait_seconds = total_wait / len(promoted_entries)

    cancelled_count = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.course_id == course_id,
        models.WaitlistEntry.status == "cancelled"
    ).count()

    return {
        "course_id": course_id,
        "current_waitlist_length": current_waitlist_length,
        "avg_promotion_wait_seconds": avg_wait_seconds,
        "cancelled_waitlist_count": cancelled_count
    }


def _enrich_course_with_counts(db: Session, course: models.Course) -> models.Course:
    course.enrolled_count = _get_enrolled_count(db, course.id)
    course.waitlist_count = _get_waiting_waitlist_count(db, course.id)
    return course


def _get_enrolled_count(db: Session, course_id: int) -> int:
    return db.query(models.Enrollment).filter(
        models.Enrollment.course_id == course_id
    ).count()


def _get_waiting_waitlist_count(db: Session, course_id: int) -> int:
    return db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.course_id == course_id,
        models.WaitlistEntry.status == "waiting"
    ).count()


def _promote_next_waitlist_user(db: Session, course_id: int) -> None:
    next_entry = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.course_id == course_id,
        models.WaitlistEntry.status == "waiting"
    ).order_by(models.WaitlistEntry.position.asc()).first()

    if next_entry:
        enrollment = models.Enrollment(
            course_id=course_id,
            user_name=next_entry.user_name,
            user_email=next_entry.user_email,
            user_phone=next_entry.user_phone,
            status="confirmed"
        )
        db.add(enrollment)
        next_entry.status = "promoted"
        next_entry.promoted_at = datetime.utcnow()
        db.commit()
        _recompute_waitlist_positions(db, course_id)


def _recompute_waitlist_positions(db: Session, course_id: int) -> None:
    waiting_entries = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.course_id == course_id,
        models.WaitlistEntry.status == "waiting"
    ).order_by(models.WaitlistEntry.joined_at.asc()).all()

    for idx, entry in enumerate(waiting_entries, start=1):
        entry.position = idx
    db.commit()
