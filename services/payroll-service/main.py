"""Payroll Engine Service - calculates gross→net, PAYG, super, generates payslips."""
import os
import uuid
import httpx
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role
from tax_engine import PayrollInput, calculate_payroll

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://payroll:payroll123@postgres:5432/payroll_db")
EMPLOYEE_SERVICE_URL = os.getenv("EMPLOYEE_SERVICE_URL", "http://employee-service:8001")
TIMESHEET_SERVICE_URL = os.getenv("TIMESHEET_SERVICE_URL", "http://timesheet-service:8002")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Payroll Engine Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PayrollRunDB(Base):
    __tablename__ = "payroll_runs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_name = Column(String, nullable=False)
    pay_frequency = Column(String)
    period_start = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    pay_date = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    total_gross = Column(Float, default=0)
    total_tax = Column(Float, default=0)
    total_net = Column(Float, default=0)
    total_super = Column(Float, default=0)
    employee_count = Column(Float, default=0)
    notes = Column(Text)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class PayslipDB(Base):
    __tablename__ = "payslips"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payroll_run_id = Column(String, nullable=False, index=True)
    employee_id = Column(String, nullable=False, index=True)
    employee_number = Column(String)
    full_name = Column(String)
    period_start = Column(String)
    period_end = Column(String)
    pay_date = Column(String)
    pay_frequency = Column(String)
    ordinary_hours = Column(Float, default=0)
    overtime_hours_1_5x = Column(Float, default=0)
    overtime_hours_2x = Column(Float, default=0)
    annual_leave_hours = Column(Float, default=0)
    sick_leave_hours = Column(Float, default=0)
    ordinary_pay = Column(Float, default=0)
    overtime_pay_1_5x = Column(Float, default=0)
    overtime_pay_2x = Column(Float, default=0)
    annual_leave_pay = Column(Float, default=0)
    sick_leave_pay = Column(Float, default=0)
    gross_earnings = Column(Float, default=0)
    payg_tax = Column(Float, default=0)
    medicare_levy = Column(Float, default=0)
    total_tax = Column(Float, default=0)
    net_pay = Column(Float, default=0)
    super_guarantee = Column(Float, default=0)
    super_fund_name = Column(String)
    super_member_number = Column(String)
    ytd_gross = Column(Float, default=0)
    ytd_tax = Column(Float, default=0)
    ytd_super = Column(Float, default=0)
    hourly_rate = Column(Float)
    annual_salary = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    user_id = Column(String)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class PayrollRunCreate(BaseModel):
    run_name: str
    period_start: str
    period_end: str
    pay_date: str
    pay_frequency: str = "fortnightly"
    employee_ids: Optional[List[str]] = None  # None = all active employees
    notes: Optional[str] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_audit(db: Session, event_type: str, entity_type: str, entity_id: str,
              user_id: str, details: str):
    log = AuditLogDB(event_type=event_type, entity_type=entity_type,
                     entity_id=entity_id, user_id=user_id, details=details)
    db.add(log)
    db.commit()


async def fetch_employees(token: str, employee_ids: Optional[List[str]] = None):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EMPLOYEE_SERVICE_URL}/employees",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        resp.raise_for_status()
        employees = resp.json()
        if employee_ids:
            employees = [e for e in employees if e["id"] in employee_ids]
        return employees


async def fetch_approved_timesheets(token: str, employee_id: str, period_start: str, period_end: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TIMESHEET_SERVICE_URL}/timesheets",
            params={"employee_id": employee_id, "status": "approved"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        if resp.status_code == 200:
            sheets = resp.json()
            # Filter to the payroll period
            return [s for s in sheets if s["period_start"] >= period_start and s["period_end"] <= period_end]
        return []


async def process_payroll_run(run_id: str, run_data: PayrollRunCreate,
                               token: str, user_id: str):
    """Background task: process all employees in a payroll run."""
    db = SessionLocal()
    try:
        run = db.query(PayrollRunDB).filter(PayrollRunDB.id == run_id).first()
        run.status = "processing"
        db.commit()

        employees = await fetch_employees(token, run_data.employee_ids)

        total_gross = total_tax = total_net = total_super = 0
        payslip_count = 0

        for emp in employees:
            try:
                timesheets = await fetch_approved_timesheets(
                    token, emp["id"], run_data.period_start, run_data.period_end
                )

                # Aggregate hours from all timesheets in period
                ordinary_hours = sum(t["ordinary_hours"] for t in timesheets)
                ot_1_5 = sum(t["overtime_hours_1_5x"] for t in timesheets)
                ot_2x = sum(t["overtime_hours_2x"] for t in timesheets)
                ph_hours = sum(t["public_holiday_hours"] for t in timesheets)
                al_hours = sum(t["annual_leave_hours"] for t in timesheets)
                sl_hours = sum(t["sick_leave_hours"] for t in timesheets)
                lsl_hours = sum(t["long_service_leave_hours"] for t in timesheets)

                # Default hours if no timesheets (salaried employees)
                if not timesheets and emp["employment_type"] == "full_time":
                    freq = emp.get("pay_frequency", "fortnightly")
                    hours_per_period = {"weekly": 38, "fortnightly": 76, "monthly": 164.67}
                    ordinary_hours = hours_per_period.get(freq, 76)

                inp = PayrollInput(
                    employee_id=emp["id"],
                    employee_number=emp["employee_number"],
                    first_name=emp["first_name"],
                    last_name=emp["last_name"],
                    annual_salary=emp["annual_salary"],
                    employment_type=emp["employment_type"],
                    pay_frequency=emp.get("pay_frequency", run_data.pay_frequency),
                    ordinary_hours=ordinary_hours,
                    overtime_hours_1_5x=ot_1_5,
                    overtime_hours_2x=ot_2x,
                    public_holiday_hours=ph_hours,
                    annual_leave_hours=al_hours,
                    sick_leave_hours=sl_hours,
                    long_service_leave_hours=lsl_hours,
                    hourly_rate=emp.get("hourly_rate"),
                    tax_free_threshold=emp.get("tax_free_threshold", True),
                    residency_status=emp.get("residency_status", "resident"),
                    super_fund_name=emp.get("super_fund_name", "AustralianSuper"),
                    super_member_number=emp.get("super_member_number"),
                    period_start=run_data.period_start,
                    period_end=run_data.period_end,
                )

                result = calculate_payroll(inp)

                payslip = PayslipDB(
                    payroll_run_id=run_id,
                    employee_id=result.employee_id,
                    employee_number=result.employee_number,
                    full_name=result.full_name,
                    period_start=result.period_start,
                    period_end=result.period_end,
                    pay_date=run_data.pay_date,
                    pay_frequency=result.pay_frequency,
                    ordinary_hours=result.ordinary_hours,
                    overtime_hours_1_5x=result.overtime_hours_1_5x,
                    overtime_hours_2x=result.overtime_hours_2x,
                    annual_leave_hours=result.annual_leave_hours,
                    sick_leave_hours=result.sick_leave_hours,
                    ordinary_pay=result.ordinary_pay,
                    overtime_pay_1_5x=result.overtime_pay_1_5x,
                    overtime_pay_2x=result.overtime_pay_2x,
                    annual_leave_pay=result.annual_leave_pay,
                    sick_leave_pay=result.sick_leave_pay,
                    gross_earnings=result.gross_earnings,
                    payg_tax=result.payg_tax,
                    medicare_levy=result.medicare_levy,
                    total_tax=result.total_tax,
                    net_pay=result.net_pay,
                    super_guarantee=result.super_guarantee,
                    super_fund_name=result.super_fund_name,
                    super_member_number=result.super_member_number,
                    ytd_gross=result.ytd_gross,
                    ytd_tax=result.ytd_tax,
                    ytd_super=result.ytd_super,
                    hourly_rate=result.hourly_rate,
                    annual_salary=result.annual_salary,
                )
                db.add(payslip)

                total_gross += result.gross_earnings
                total_tax += result.total_tax
                total_net += result.net_pay
                total_super += result.super_guarantee
                payslip_count += 1

            except Exception as e:
                print(f"Error processing employee {emp.get('id')}: {e}")
                continue

        db.flush()
        run.status = "completed"
        run.total_gross = round(total_gross, 2)
        run.total_tax = round(total_tax, 2)
        run.total_net = round(total_net, 2)
        run.total_super = round(total_super, 2)
        run.employee_count = payslip_count
        run.completed_at = datetime.utcnow()
        db.commit()

        log_audit(db, "PAYROLL_RUN_COMPLETED", "payroll_run", run_id, user_id,
                  f"Processed {payslip_count} employees. Gross: ${total_gross:.2f}")

    except Exception as e:
        db = SessionLocal()
        run = db.query(PayrollRunDB).filter(PayrollRunDB.id == run_id).first()
        if run:
            run.status = "failed"
            run.notes = str(e)
            db.commit()
        print(f"Payroll run failed: {e}")
    finally:
        db.close()


@app.post("/payroll-runs", status_code=201)
async def create_payroll_run(data: PayrollRunCreate, background_tasks: BackgroundTasks,
                              db: Session = Depends(get_db),
                              user=Depends(require_role("admin", "payroll_officer")),
                              credentials=Depends(__import__("fastapi.security", fromlist=["HTTPBearer"]).HTTPBearer())):
    run = PayrollRunDB(
        run_name=data.run_name,
        pay_frequency=data.pay_frequency,
        period_start=data.period_start,
        period_end=data.period_end,
        pay_date=data.pay_date,
        notes=data.notes,
        created_by=user.get("email"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(
        process_payroll_run, run.id, data, credentials.credentials, user.get("user_id", "")
    )

    return {"message": "Payroll run started", "run_id": run.id, "status": "processing"}


@app.get("/payroll-runs")
def list_payroll_runs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    runs = db.query(PayrollRunDB).order_by(PayrollRunDB.created_at.desc()).all()
    return [
        {
            "id": r.id, "run_name": r.run_name, "period_start": r.period_start,
            "period_end": r.period_end, "pay_date": r.pay_date, "status": r.status,
            "total_gross": r.total_gross, "total_tax": r.total_tax, "total_net": r.total_net,
            "total_super": r.total_super, "employee_count": r.employee_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@app.get("/payroll-runs/{run_id}")
def get_payroll_run(run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    run = db.query(PayrollRunDB).filter(PayrollRunDB.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    payslips = db.query(PayslipDB).filter(PayslipDB.payroll_run_id == run_id).all()
    return {
        "run": {
            "id": run.id, "run_name": run.run_name, "status": run.status,
            "period_start": run.period_start, "period_end": run.period_end,
            "pay_date": run.pay_date, "total_gross": run.total_gross,
            "total_tax": run.total_tax, "total_net": run.total_net,
            "total_super": run.total_super, "employee_count": run.employee_count,
        },
        "payslips": [
            {c.name: getattr(p, c.name) for c in p.__table__.columns}
            for p in payslips
        ]
    }


@app.get("/payslips")
def list_payslips(employee_id: Optional[str] = None, payroll_run_id: Optional[str] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(PayslipDB)
    if employee_id:
        q = q.filter(PayslipDB.employee_id == employee_id)
    if payroll_run_id:
        q = q.filter(PayslipDB.payroll_run_id == payroll_run_id)
    return [{c.name: getattr(p, c.name) for c in p.__table__.columns}
            for p in q.order_by(PayslipDB.created_at.desc()).all()]


@app.get("/payslips/{payslip_id}")
def get_payslip(payslip_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(PayslipDB).filter(PayslipDB.id == payslip_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payslip not found")
    return {c.name: getattr(p, c.name) for c in p.__table__.columns}


@app.get("/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    logs = db.query(AuditLogDB).order_by(AuditLogDB.created_at.desc()).limit(200).all()
    return [{c.name: getattr(l, c.name) for c in l.__table__.columns} for l in logs]


@app.get("/health")
def health():
    return {"status": "ok", "service": "payroll-service"}
