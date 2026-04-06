"""Reporting Service - payroll summaries, tax reports, super reports as CSV."""
import os
import io
import csv
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://payroll:payroll123@postgres:5432/reporting_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Reporting Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ReportDB(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_type = Column(String)
    report_name = Column(String)
    parameters = Column(Text)
    row_count = Column(Float, default=0)
    generated_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def generate_csv(headers: List[str], rows: List[Dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PayrollSummaryRequest(BaseModel):
    payroll_run_id: str
    run_data: Dict[str, Any]
    payslips: List[Dict[str, Any]]


class TaxReportRequest(BaseModel):
    financial_year: str
    payslips: List[Dict[str, Any]]


class SuperReportRequest(BaseModel):
    period_start: str
    period_end: str
    payslips: List[Dict[str, Any]]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/reports/payroll-summary")
def payroll_summary_report(req: PayrollSummaryRequest,
                            format: str = "json",
                            db: Session = Depends(get_db),
                            user=Depends(get_current_user)):
    """Payroll run summary report."""
    run = req.run_data
    payslips = req.payslips

    rows = []
    for ps in payslips:
        rows.append({
            "Employee Number": ps.get("employee_number"),
            "Full Name": ps.get("full_name"),
            "Period Start": ps.get("period_start"),
            "Period End": ps.get("period_end"),
            "Pay Date": ps.get("pay_date"),
            "Ordinary Hours": ps.get("ordinary_hours", 0),
            "OT Hours 1.5x": ps.get("overtime_hours_1_5x", 0),
            "OT Hours 2x": ps.get("overtime_hours_2x", 0),
            "Leave Hours": ps.get("annual_leave_hours", 0),
            "Ordinary Pay": f"${ps.get('ordinary_pay', 0):.2f}",
            "Overtime Pay": f"${ps.get('overtime_pay_1_5x', 0) + ps.get('overtime_pay_2x', 0):.2f}",
            "Leave Pay": f"${ps.get('annual_leave_pay', 0) + ps.get('sick_leave_pay', 0):.2f}",
            "Gross Earnings": f"${ps.get('gross_earnings', 0):.2f}",
            "PAYG Tax": f"${ps.get('payg_tax', 0):.2f}",
            "Net Pay": f"${ps.get('net_pay', 0):.2f}",
            "Super Guarantee": f"${ps.get('super_guarantee', 0):.2f}",
            "Super Fund": ps.get("super_fund_name"),
            "YTD Gross": f"${ps.get('ytd_gross', 0):.2f}",
            "YTD Tax": f"${ps.get('ytd_tax', 0):.2f}",
            "YTD Super": f"${ps.get('ytd_super', 0):.2f}",
        })

    # Log report generation
    report = ReportDB(
        report_type="PAYROLL_SUMMARY",
        report_name=f"Payroll Summary - {run.get('period_start')} to {run.get('period_end')}",
        row_count=len(rows),
        generated_by=user.get("email"),
    )
    db.add(report)
    db.commit()

    if format == "csv":
        headers = list(rows[0].keys()) if rows else []
        csv_content = generate_csv(headers, rows)
        filename = f"payroll_summary_{run.get('period_end', 'report')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # JSON response with totals
    return {
        "report_type": "PAYROLL_SUMMARY",
        "generated_at": datetime.utcnow().isoformat(),
        "period_start": run.get("period_start"),
        "period_end": run.get("period_end"),
        "totals": {
            "gross": run.get("total_gross"),
            "tax": run.get("total_tax"),
            "net": run.get("total_net"),
            "super": run.get("total_super"),
            "employee_count": run.get("employee_count"),
        },
        "rows": rows,
    }


@app.post("/reports/tax-report")
def tax_report(req: TaxReportRequest, format: str = "json",
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Annual PAYG tax report per employee."""
    # Aggregate by employee
    emp_totals: Dict[str, Dict] = {}
    for ps in req.payslips:
        eid = ps.get("employee_id")
        if eid not in emp_totals:
            emp_totals[eid] = {
                "Employee Number": ps.get("employee_number"),
                "Full Name": ps.get("full_name"),
                "Financial Year": req.financial_year,
                "Total Gross": 0,
                "Total PAYG Tax": 0,
                "Total Medicare": 0,
                "Total Net Pay": 0,
                "Total Super": 0,
            }
        emp_totals[eid]["Total Gross"] += ps.get("gross_earnings", 0)
        emp_totals[eid]["Total PAYG Tax"] += ps.get("payg_tax", 0)
        emp_totals[eid]["Total Medicare"] += ps.get("medicare_levy", 0)
        emp_totals[eid]["Total Net Pay"] += ps.get("net_pay", 0)
        emp_totals[eid]["Total Super"] += ps.get("super_guarantee", 0)

    rows = []
    for eid, data in emp_totals.items():
        rows.append({
            **data,
            "Total Gross": f"${data['Total Gross']:.2f}",
            "Total PAYG Tax": f"${data['Total PAYG Tax']:.2f}",
            "Total Medicare": f"${data['Total Medicare']:.2f}",
            "Total Net Pay": f"${data['Total Net Pay']:.2f}",
            "Total Super": f"${data['Total Super']:.2f}",
        })

    report = ReportDB(
        report_type="TAX_REPORT",
        report_name=f"Tax Report FY{req.financial_year}",
        row_count=len(rows),
        generated_by=user.get("email"),
    )
    db.add(report)
    db.commit()

    if format == "csv":
        headers = list(rows[0].keys()) if rows else []
        csv_content = generate_csv(headers, rows)
        return Response(
            content=csv_content, media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=tax_report_{req.financial_year}.csv"}
        )

    return {"report_type": "TAX_REPORT", "financial_year": req.financial_year, "rows": rows}


@app.post("/reports/super-report")
def super_report(req: SuperReportRequest, format: str = "json",
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Superannuation contributions report."""
    rows = []
    for ps in req.payslips:
        rows.append({
            "Employee Number": ps.get("employee_number"),
            "Full Name": ps.get("full_name"),
            "Period Start": ps.get("period_start"),
            "Period End": ps.get("period_end"),
            "Gross OTE": f"${ps.get('ordinary_pay', 0) + ps.get('annual_leave_pay', 0):.2f}",
            "Super Rate": "11%",
            "Employer Super": f"${ps.get('super_guarantee', 0):.2f}",
            "Super Fund": ps.get("super_fund_name"),
            "Member Number": ps.get("super_member_number"),
            "YTD Super": f"${ps.get('ytd_super', 0):.2f}",
        })

    report = ReportDB(
        report_type="SUPER_REPORT",
        report_name=f"Super Report {req.period_start} to {req.period_end}",
        row_count=len(rows),
        generated_by=user.get("email"),
    )
    db.add(report)
    db.commit()

    if format == "csv":
        headers = list(rows[0].keys()) if rows else []
        csv_content = generate_csv(headers, rows)
        return Response(
            content=csv_content, media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=super_report.csv"}
        )

    total_super = sum(ps.get("super_guarantee", 0) for ps in req.payslips)
    return {
        "report_type": "SUPER_REPORT",
        "period_start": req.period_start,
        "period_end": req.period_end,
        "total_super": round(total_super, 2),
        "employee_count": len(rows),
        "rows": rows,
    }


@app.get("/reports/history")
def report_history(db: Session = Depends(get_db), user=Depends(get_current_user)):
    reports = db.query(ReportDB).order_by(ReportDB.created_at.desc()).limit(100).all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in reports]


@app.get("/health")
def health():
    return {"status": "ok", "service": "reporting-service"}
