from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    capacity = Column(Integer, nullable=False)
    waitlist_capacity = Column(Integer, nullable=True)
    instructor = Column(String(100), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    enrollments = relationship("Enrollment", back_populates="course")
    waitlist = relationship("WaitlistEntry", back_populates="course")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    user_name = Column(String(100), nullable=False)
    user_email = Column(String(200), nullable=False)
    user_phone = Column(String(20), nullable=True)
    status = Column(String(20), default="confirmed")
    enrolled_at = Column(DateTime, server_default=func.now())

    course = relationship("Course", back_populates="enrollments")


class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    user_name = Column(String(100), nullable=False)
    user_email = Column(String(200), nullable=False)
    user_phone = Column(String(20), nullable=True)
    position = Column(Integer, nullable=False)
    joined_at = Column(DateTime, server_default=func.now())

    course = relationship("Course", back_populates="waitlist")
