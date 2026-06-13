from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


class CourseBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    capacity: int = Field(..., gt=0)
    waitlist_capacity: Optional[int] = Field(None, ge=0)
    instructor: Optional[str] = Field(None, max_length=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    capacity: Optional[int] = Field(None, gt=0)
    waitlist_capacity: Optional[int] = Field(None, ge=0)
    instructor: Optional[str] = Field(None, max_length=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class Course(CourseBase):
    id: int
    created_at: datetime
    enrolled_count: int = 0
    waitlist_count: int = 0

    class Config:
        from_attributes = True


class EnrollmentBase(BaseModel):
    user_name: str = Field(..., max_length=100)
    user_email: str = Field(..., max_length=200)
    user_phone: Optional[str] = Field(None, max_length=20)


class EnrollmentCreate(EnrollmentBase):
    pass


class Enrollment(EnrollmentBase):
    id: int
    course_id: int
    status: str
    enrolled_at: datetime

    class Config:
        from_attributes = True


class WaitlistEntryBase(BaseModel):
    user_name: str = Field(..., max_length=100)
    user_email: str = Field(..., max_length=200)
    user_phone: Optional[str] = Field(None, max_length=20)


class WaitlistEntryCreate(WaitlistEntryBase):
    pass


class WaitlistEntry(WaitlistEntryBase):
    id: int
    course_id: int
    position: int
    joined_at: datetime

    class Config:
        from_attributes = True


class EnrollmentResult(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    position: Optional[int] = None
