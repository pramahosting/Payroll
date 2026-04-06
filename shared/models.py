"""Shared Pydantic models and enums used across all services."""
from enum import Enum
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CASUAL = "casual"
    CONTRACT = "contract"


class LeaveType(str, Enum):
    ANNUAL = "annual"
    SICK = "sick"
    LONG_SERVICE = "long_service"
    PERSONAL = "personal"
    UNPAID = "unpaid"


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"


class UserRole(str, Enum):
    ADMIN = "admin"
    PAYROLL_OFFICER = "payroll_officer"
    EMPLOYEE = "employee"


class TokenData(BaseModel):
    user_id: str
    email: str
    role: UserRole


class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
