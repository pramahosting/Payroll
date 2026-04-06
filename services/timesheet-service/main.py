"""Timesheet Service - captures hours, leave, and overtime."""
import os
import uuid
from datetime import datetime, date
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role
from models import LeaveType

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://payroll:payroll123@postgres:5432/timesheet_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Timesheet Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TimesheetDB(Base):
    __tablename__ = "timesheets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, nullable=False, index=True)
    period_start = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    ordinary_hours = Column(Float, default=0)
    overtime_hours_1_5x = Column(Float, default=0)   # time and a half
    overtime_hours_2x = Column(Float, default=0)     # double time
    public_holiday_hours = Column(Float, default=0)
    annual_leave_hours = Column(Float, default=0)
    sick_leave_hours = Column(Float, default=0)
    long_service_leave_hours = Column(Float, default=0)
    unpaid_leave_hours = Column(Float, default=0)
    notes = Column(String)
    status = Column(String, default="draft")  # draft, submitted, approved, rejected
    submitted_at = Column(DateTime)
    approved_at = Column(DateTime)
    approved_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LeaveRequestDB(Base):
    __tablename__ = "leave_requests"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, nullable=False, index=True)
    leave_type = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    hours_requested = Column(Float, nullable=False)
    reason = Column(String)
    status = Column(String, default="pending")  # pending, approved, rejected
    approved_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class TimesheetCreate(BaseModel):
    employee_id: str
    period_start: str
    period_end: str
    ordinary_hours: float = 0
    overtime_hours_1_5x: float = 0
    overtime_hours_2x: float = 0
    public_holiday_hours: float = 0
    annual_leave_hours: float = 0
    sick_leave_hours: float = 0
    long_service_leave_hours: float = 0
    unpaid_leave_hours: float = 0
    notes: Optional[str] = None


class TimesheetResponse(BaseModel):
    id: str
    employee_id: str
    period_start: str
    period_end: str
    ordinary_hours: float
    overtime_hours_1_5x: float
    overtime_hours_2x: float
    public_holiday_hours: float
    annual_leave_hours: float
    sick_leave_hours: float
    long_service_leave_hours: float
    unpaid_leave_hours: float
    notes: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    total_hours: float = 0

    class Config:
        from_attributes = True

    @classmethod
    def from_db(cls, ts: TimesheetDB):
        d = {c.name: getattr(ts, c.name) for c in ts.__table__.columns}
        d["total_hours"] = (ts.ordinary_hours + ts.overtime_hours_1_5x +
                            ts.overtime_hours_2x + ts.public_holiday_hours +
                            ts.annual_leave_hours + ts.sick_leave_hours)
        return cls(**d)


class LeaveRequestCreate(BaseModel):
    employee_id: str
    leave_type: LeaveType
    start_date: str
    end_date: str
    hours_requested: float
    reason: Optional[str] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/timesheets", status_code=201)
def create_timesheet(data: TimesheetCreate, db: Session = Depends(get_db),
                     user=Depends(get_current_user)):
    ts = TimesheetDB(**data.dict())
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return TimesheetResponse.from_db(ts)


@app.get("/timesheets")
def list_timesheets(employee_id: Optional[str] = None, status: Optional[str] = None,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(TimesheetDB)
    if employee_id:
        q = q.filter(TimesheetDB.employee_id == employee_id)
    if status:
        q = q.filter(TimesheetDB.status == status)
    return [TimesheetResponse.from_db(ts) for ts in q.order_by(TimesheetDB.period_start.desc()).all()]


@app.get("/timesheets/{timesheet_id}")
def get_timesheet(timesheet_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ts = db.query(TimesheetDB).filter(TimesheetDB.id == timesheet_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return TimesheetResponse.from_db(ts)


@app.post("/timesheets/{timesheet_id}/submit")
def submit_timesheet(timesheet_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ts = db.query(TimesheetDB).filter(TimesheetDB.id == timesheet_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    if ts.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot submit timesheet in '{ts.status}' status")
    ts.status = "submitted"
    ts.submitted_at = datetime.utcnow()
    db.commit()
    return {"message": "Timesheet submitted for approval", "id": timesheet_id}


@app.post("/timesheets/{timesheet_id}/approve")
def approve_timesheet(timesheet_id: str, db: Session = Depends(get_db),
                      user=Depends(require_role("admin", "payroll_officer"))):
    ts = db.query(TimesheetDB).filter(TimesheetDB.id == timesheet_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    ts.status = "approved"
    ts.approved_at = datetime.utcnow()
    ts.approved_by = user.get("email")
    db.commit()
    return {"message": "Timesheet approved", "id": timesheet_id}


@app.post("/timesheets/{timesheet_id}/reject")
def reject_timesheet(timesheet_id: str, db: Session = Depends(get_db),
                     user=Depends(require_role("admin", "payroll_officer"))):
    ts = db.query(TimesheetDB).filter(TimesheetDB.id == timesheet_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    ts.status = "rejected"
    db.commit()
    return {"message": "Timesheet rejected", "id": timesheet_id}


@app.post("/leave-requests", status_code=201)
def create_leave_request(data: LeaveRequestCreate, db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    req = LeaveRequestDB(**data.dict())
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@app.get("/leave-requests")
def list_leave_requests(employee_id: Optional[str] = None, db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    q = db.query(LeaveRequestDB)
    if employee_id:
        q = q.filter(LeaveRequestDB.employee_id == employee_id)
    return q.order_by(LeaveRequestDB.created_at.desc()).all()


@app.get("/health")
def health():
    return {"status": "ok", "service": "timesheet-service"}
