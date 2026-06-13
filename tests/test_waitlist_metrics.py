import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app import models


def create_test_course(db: Session, capacity: int = 2, waitlist_capacity: int = 10) -> models.Course:
    course = models.Course(
        title="Test Course",
        description="Test Description",
        capacity=capacity,
        waitlist_capacity=waitlist_capacity,
        instructor="Test Instructor"
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def test_waitlist_metrics_empty_queue_returns_zeros(client: TestClient, db_session: Session):
    course = create_test_course(db_session, capacity=5)

    response = client.get(f"/courses/{course.id}/waitlist-metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["course_id"] == course.id
    assert data["current_waitlist_length"] == 0
    assert data["avg_promotion_wait_seconds"] == 0.0
    assert data["cancelled_waitlist_count"] == 0


def test_waitlist_metrics_mixed_state_computes_correctly(client: TestClient, db_session: Session):
    course = create_test_course(db_session, capacity=3, waitlist_capacity=10)
    course_id = course.id
    now = datetime.utcnow()

    db_session.add(models.Enrollment(
        course_id=course_id, user_name="E1", user_email="e1@test.com"
    ))
    db_session.add(models.Enrollment(
        course_id=course_id, user_name="E2", user_email="e2@test.com"
    ))
    db_session.add(models.Enrollment(
        course_id=course_id, user_name="E3", user_email="e3@test.com"
    ))

    wait1 = models.WaitlistEntry(
        course_id=course_id, user_name="W1", user_email="w1@test.com",
        position=1, status="waiting", joined_at=now - timedelta(hours=5)
    )
    wait2 = models.WaitlistEntry(
        course_id=course_id, user_name="W2", user_email="w2@test.com",
        position=2, status="waiting", joined_at=now - timedelta(hours=3)
    )
    wait3 = models.WaitlistEntry(
        course_id=course_id, user_name="W3", user_email="w3@test.com",
        position=3, status="waiting", joined_at=now - timedelta(hours=1)
    )

    promoted1 = models.WaitlistEntry(
        course_id=course_id, user_name="P1", user_email="p1@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(hours=10),
        promoted_at=now - timedelta(hours=8)
    )
    promoted2 = models.WaitlistEntry(
        course_id=course_id, user_name="P2", user_email="p2@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(hours=6),
        promoted_at=now - timedelta(hours=2)
    )

    old_promoted = models.WaitlistEntry(
        course_id=course_id, user_name="OP1", user_email="op1@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(days=30),
        promoted_at=now - timedelta(days=29)
    )

    cancelled1 = models.WaitlistEntry(
        course_id=course_id, user_name="C1", user_email="c1@test.com",
        position=0, status="cancelled",
        joined_at=now - timedelta(hours=4)
    )
    cancelled2 = models.WaitlistEntry(
        course_id=course_id, user_name="C2", user_email="c2@test.com",
        position=0, status="cancelled",
        joined_at=now - timedelta(days=20)
    )

    for entry in [wait1, wait2, wait3, promoted1, promoted2, old_promoted, cancelled1, cancelled2]:
        db_session.add(entry)

    db_session.commit()

    response = client.get(f"/courses/{course_id}/waitlist-metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["course_id"] == course_id
    assert data["current_waitlist_length"] == 3
    assert data["cancelled_waitlist_count"] == 2

    avg_wait = (2 * 3600 + 4 * 3600) / 2
    assert data["avg_promotion_wait_seconds"] == pytest.approx(avg_wait, rel=1e-3)


def test_waitlist_metrics_nonexistent_course_returns_404(client: TestClient, db_session: Session):
    response = client.get("/courses/9999/waitlist-metrics")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_waitlist_metrics_default_days_is_7(client: TestClient, db_session: Session):
    course = create_test_course(db_session, capacity=3, waitlist_capacity=10)
    course_id = course.id
    now = datetime.utcnow()

    promoted_recent = models.WaitlistEntry(
        course_id=course_id, user_name="PR", user_email="pr@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(days=5),
        promoted_at=now - timedelta(days=3)
    )
    promoted_old = models.WaitlistEntry(
        course_id=course_id, user_name="PO", user_email="po@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(days=20),
        promoted_at=now - timedelta(days=10)
    )

    db_session.add_all([promoted_recent, promoted_old])
    db_session.commit()

    response_default = client.get(f"/courses/{course_id}/waitlist-metrics")
    response_explicit_7 = client.get(f"/courses/{course_id}/waitlist-metrics?days=7")

    assert response_default.status_code == 200
    assert response_explicit_7.status_code == 200

    data_default = response_default.json()
    data_7 = response_explicit_7.json()

    expected_avg = 2 * 24 * 3600
    assert data_default["avg_promotion_wait_seconds"] == pytest.approx(expected_avg, rel=1e-3)
    assert data_7["avg_promotion_wait_seconds"] == pytest.approx(expected_avg, rel=1e-3)
    assert data_default == data_7


def test_waitlist_metrics_days_30_returns_30_day_avg(client: TestClient, db_session: Session):
    course = create_test_course(db_session, capacity=3, waitlist_capacity=10)
    course_id = course.id
    now = datetime.utcnow()

    promoted_5d = models.WaitlistEntry(
        course_id=course_id, user_name="P5", user_email="p5@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(days=5),
        promoted_at=now - timedelta(days=3)
    )
    promoted_15d = models.WaitlistEntry(
        course_id=course_id, user_name="P15", user_email="p15@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(days=20),
        promoted_at=now - timedelta(days=15)
    )
    promoted_60d = models.WaitlistEntry(
        course_id=course_id, user_name="P60", user_email="p60@test.com",
        position=0, status="promoted",
        joined_at=now - timedelta(days=80),
        promoted_at=now - timedelta(days=60)
    )

    db_session.add_all([promoted_5d, promoted_15d, promoted_60d])
    db_session.commit()

    response = client.get(f"/courses/{course_id}/waitlist-metrics?days=30")

    assert response.status_code == 200
    data = response.json()

    avg_30d = (2 * 24 * 3600 + 5 * 24 * 3600) / 2
    assert data["avg_promotion_wait_seconds"] == pytest.approx(avg_30d, rel=1e-3)


def test_waitlist_metrics_days_120_returns_400(client: TestClient, db_session: Session):
    course = create_test_course(db_session, capacity=5)

    response = client.get(f"/courses/{course.id}/waitlist-metrics?days=120")

    assert response.status_code == 400
    assert "90" in response.json()["detail"]
    assert "maximum" in response.json()["detail"].lower()
