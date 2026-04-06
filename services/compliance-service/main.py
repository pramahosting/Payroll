"""Compliance Service - STP Phase 2 reporting, PAYG, ATO submission simulation."""
import os
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://payroll:payroll123@postgres:5432/compliance_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Compliance Service", version="1.0.0",
              description="STP Phase 2, PAYG and ATO compliance reporting")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class STPSubmissionDB(Base):
    __tablename__ = "stp_submissions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_type = Column(String)  # PAY_EVENT, UPDATE_EVENT, FINALISATION
    payroll_run_id = Column(String)
    abn = Column(String)
    software_id = Column(String)
    submission_date = Column(String)
    period_start = Column(String)
    period_end = Column(String)
    employee_count = Column(Float, default=0)
    total_gross = Column(Float, default=0)
    total_tax = Column(Float, default=0)
    total_super = Column(Float, default=0)
    payload_json = Column(Text)  # full STP payload
    status = Column(String, default="draft")  # draft, validated, submitted, accepted, rejected
    ato_reference = Column(String)  # mock ATO reference number
    validation_errors = Column(Text)
    submitted_by = Column(String)
    submitted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class PAYGSummaryDB(Base):
    __tablename__ = "payg_summaries"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    financial_year = Column(String)  # e.g. "2023-24"
    employee_id = Column(String)
    employee_number = Column(String)
    full_name = Column(String)
    tfn = Column(String)
    gross_payments = Column(Float, default=0)
    total_tax_withheld = Column(Float, default=0)
    reportable_super = Column(Float, default=0)
    total_super = Column(Float, default=0)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# ── STP Phase 2 Payload Builder ───────────────────────────────────────────────

def build_stp_payload(payroll_data: Dict[str, Any], abn: str) -> Dict:
    """
    Build STP Phase 2 compliant XML/JSON payload structure.
    This mirrors the ATO's STP Phase 2 specification.
    """
    payslips = payroll_data.get("payslips", [])
    run = payroll_data.get("run", {})

    employees_data = []
    for ps in payslips:
        emp_data = {
            "employeeId": ps.get("employee_id"),
            "employeeNumber": ps.get("employee_number"),
            "fullName": ps.get("full_name"),
            # Income types per STP Phase 2
            "incomeType": "SAL",  # SAL=Salary, LAB=Labour, CLO=Closely Held
            "payrollId": ps.get("id"),
            "payPeriod": {
                "startDate": ps.get("period_start"),
                "endDate": ps.get("period_end"),
                "paymentDate": ps.get("pay_date"),
            },
            "earnings": {
                "ordinaryTimeEarnings": ps.get("ordinary_pay", 0),
                "overtimeEarnings": (ps.get("overtime_pay_1_5x", 0) + ps.get("overtime_pay_2x", 0)),
                "leaveEarnings": ps.get("annual_leave_pay", 0) + ps.get("sick_leave_pay", 0),
                "grossPayments": ps.get("gross_earnings", 0),
            },
            "deductions": {
                "taxWithheld": ps.get("total_tax", 0),
                "medicareLevy": ps.get("medicare_levy", 0),
            },
            "superannuation": {
                "employerContributions": ps.get("super_guarantee", 0),
                "fundName": ps.get("super_fund_name"),
                "memberNumber": ps.get("super_member_number"),
                "contributionType": "OTE",  # Ordinary Time Earnings
            },
            "ytd": {
                "grossPayments": ps.get("ytd_gross", 0),
                "taxWithheld": ps.get("ytd_tax", 0),
                "superannuation": ps.get("ytd_super", 0),
            }
        }
        employees_data.append(emp_data)

    return {
        "messageId": str(uuid.uuid4()),
        "messageTimestamp": datetime.utcnow().isoformat() + "Z",
        "softwareId": "AU-PAYROLL-PLATFORM-v1.0",
        "softwareVersion": "1.0.0",
        "payEventType": "REGULAR",
        "submitter": {
            "abn": abn,
            "name": "AU Payroll Platform",
        },
        "employer": {
            "abn": abn,
            "withholdingPayerNumber": abn,
        },
        "payEvent": {
            "payPeriod": {
                "startDate": run.get("period_start"),
                "endDate": run.get("period_end"),
                "paymentDate": run.get("pay_date"),
            },
            "payrollId": run.get("id"),
            "employeeCount": len(payslips),
            "totalGrossPayments": run.get("total_gross", 0),
            "totalTaxWithheld": run.get("total_tax", 0),
            "totalEmployerSuperContributions": run.get("total_super", 0),
        },
        "employees": employees_data,
        # STP Phase 2 specific fields
        "stpPhase": "2",
        "declarationAccepted": True,
        "declarationTimestamp": datetime.utcnow().isoformat() + "Z",
    }


def validate_stp_payload(payload: Dict) -> List[str]:
    """Validate STP payload against ATO business rules."""
    errors = []

    if not payload.get("submitter", {}).get("abn"):
        errors.append("ABN is required")

    employees = payload.get("employees", [])
    if not employees:
        errors.append("At least one employee record is required")

    for emp in employees:
        emp_id = emp.get("employeeNumber", "unknown")
        if not emp.get("fullName"):
            errors.append(f"Employee {emp_id}: Full name is required")
        if emp.get("earnings", {}).get("grossPayments", 0) < 0:
            errors.append(f"Employee {emp_id}: Gross payments cannot be negative")
        if emp.get("deductions", {}).get("taxWithheld", 0) < 0:
            errors.append(f"Employee {emp_id}: Tax withheld cannot be negative")
        super_amt = emp.get("superannuation", {}).get("employerContributions", 0)
        gross = emp.get("earnings", {}).get("grossPayments", 0)
        if gross > 0 and super_amt < 0:
            errors.append(f"Employee {emp_id}: Super contributions cannot be negative")

    return errors


# ── Schemas ───────────────────────────────────────────────────────────────────

class STPSubmissionRequest(BaseModel):
    payroll_run_id: str
    payroll_data: Dict[str, Any]  # full payroll run + payslips from payroll service
    abn: str = "12345678901"      # company ABN
    submission_type: str = "PAY_EVENT"


class PAYGSummaryRequest(BaseModel):
    financial_year: str
    employees_data: List[Dict[str, Any]]  # list of YTD data per employee


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/stp/prepare", status_code=201)
def prepare_stp_submission(req: STPSubmissionRequest, db: Session = Depends(get_db),
                            user=Depends(require_role("admin", "payroll_officer"))):
    """Build and validate an STP Phase 2 payload ready for submission."""
    payload = build_stp_payload(req.payroll_data, req.abn)
    errors = validate_stp_payload(payload)

    run = req.payroll_data.get("run", {})
    payslips = req.payroll_data.get("payslips", [])

    sub = STPSubmissionDB(
        submission_type=req.submission_type,
        payroll_run_id=req.payroll_run_id,
        abn=req.abn,
        software_id="AU-PAYROLL-v1.0",
        submission_date=datetime.utcnow().strftime("%Y-%m-%d"),
        period_start=run.get("period_start"),
        period_end=run.get("period_end"),
        employee_count=len(payslips),
        total_gross=run.get("total_gross", 0),
        total_tax=run.get("total_tax", 0),
        total_super=run.get("total_super", 0),
        payload_json=json.dumps(payload),
        status="validated" if not errors else "validation_failed",
        validation_errors=json.dumps(errors) if errors else None,
        submitted_by=user.get("email"),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {
        "submission_id": sub.id,
        "status": sub.status,
        "validation_errors": errors,
        "payload_preview": {
            "employee_count": len(payslips),
            "total_gross": run.get("total_gross"),
            "total_tax": run.get("total_tax"),
            "total_super": run.get("total_super"),
        }
    }


@app.post("/stp/{submission_id}/submit")
def submit_to_ato(submission_id: str, db: Session = Depends(get_db),
                  user=Depends(require_role("admin", "payroll_officer"))):
    """Simulate submission to ATO (mock - returns fake ATO reference)."""
    sub = db.query(STPSubmissionDB).filter(STPSubmissionDB.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status not in ("validated", "draft"):
        raise HTTPException(status_code=400, detail=f"Cannot submit in status '{sub.status}'")

    # Simulate ATO response
    ato_ref = f"ATO-STP-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    sub.status = "submitted"
    sub.ato_reference = ato_ref
    sub.submitted_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Successfully submitted to ATO (simulated)",
        "ato_reference": ato_ref,
        "submission_id": submission_id,
        "status": "submitted",
    }


@app.get("/stp/submissions")
def list_submissions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    subs = db.query(STPSubmissionDB).order_by(STPSubmissionDB.created_at.desc()).all()
    return [
        {
            "id": s.id, "submission_type": s.submission_type, "payroll_run_id": s.payroll_run_id,
            "period_start": s.period_start, "period_end": s.period_end,
            "employee_count": s.employee_count, "total_gross": s.total_gross,
            "status": s.status, "ato_reference": s.ato_reference,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        }
        for s in subs
    ]


@app.post("/payg-summaries/generate")
def generate_payg_summaries(req: PAYGSummaryRequest, db: Session = Depends(get_db),
                             user=Depends(require_role("admin", "payroll_officer"))):
    """Generate Payment Summaries (Group Certificates) for the financial year."""
    created = []
    for emp in req.employees_data:
        summary = PAYGSummaryDB(
            financial_year=req.financial_year,
            employee_id=emp.get("employee_id"),
            employee_number=emp.get("employee_number"),
            full_name=emp.get("full_name"),
            tfn=emp.get("tfn", "***-***-***"),  # masked
            gross_payments=emp.get("ytd_gross", 0),
            total_tax_withheld=emp.get("ytd_tax", 0),
            total_super=emp.get("ytd_super", 0),
            status="draft",
        )
        db.add(summary)
        created.append(summary)

    db.commit()
    return {"message": f"Generated {len(created)} PAYG summaries for {req.financial_year}",
            "count": len(created)}


@app.get("/payg-summaries")
def list_payg_summaries(financial_year: Optional[str] = None, db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    q = db.query(PAYGSummaryDB)
    if financial_year:
        q = q.filter(PAYGSummaryDB.financial_year == financial_year)
    return [{c.name: getattr(s, c.name) for c in s.__table__.columns}
            for s in q.order_by(PAYGSummaryDB.created_at.desc()).all()]


@app.get("/health")
def health():
    return {"status": "ok", "service": "compliance-service"}
