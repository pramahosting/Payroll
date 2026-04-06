"""Payments Service - ABA file generation, bank payments, super batches."""
import os
import uuid
import io
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://payroll:payroll123@postgres:5432/payments_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Payments Service", version="1.0.0",
              description="ABA file generation and payment batch management")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PaymentBatchDB(Base):
    __tablename__ = "payment_batches"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_type = Column(String)  # SALARY, SUPERANNUATION
    payroll_run_id = Column(String)
    pay_date = Column(String)
    total_amount = Column(Float, default=0)
    transaction_count = Column(Float, default=0)
    aba_file_content = Column(Text)
    status = Column(String, default="pending")  # pending, approved, sent, failed
    bank_bsb = Column(String)  # employer's bank BSB
    bank_account = Column(String)  # employer's account
    bank_name = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)


class PaymentTransactionDB(Base):
    __tablename__ = "payment_transactions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String, nullable=False, index=True)
    employee_id = Column(String)
    employee_number = Column(String)
    full_name = Column(String)
    bsb = Column(String)
    account_number = Column(String)
    account_name = Column(String)
    amount = Column(Float)
    description = Column(String)
    transaction_type = Column(String)  # CREDIT, DEBIT
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class SuperBatchDB(Base):
    __tablename__ = "super_batches"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payroll_run_id = Column(String)
    quarter = Column(String)  # e.g. "Q1 2024"
    due_date = Column(String)
    total_amount = Column(Float, default=0)
    employee_count = Column(Float, default=0)
    status = Column(String, default="pending")  # pending, submitted, paid
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime)


Base.metadata.create_all(bind=engine)


# ── ABA File Generator ────────────────────────────────────────────────────────

def generate_aba_file(batch_id: str, transactions: List[Dict], employer_bsb: str,
                       employer_account: str, employer_name: str, pay_date: str) -> str:
    """
    Generate ABA (Australian Bankers' Association) file format.
    Spec: https://www.cemtexaba.com/aba-format
    """
    lines = []

    # ── Descriptive Record (Type 0) ──────────────────────────────────────
    # BSB (7), Filler (1), Sequence (6), Bank (3), Filler (7), User name (26),
    # APCA (6), Description (12), Date (6), Time (4), Filler (36)
    date_str = datetime.strptime(pay_date, "%Y-%m-%d").strftime("%d%m%y")
    bank_code = "NAB"  # mock bank
    user_name = f"{employer_name:<26}"[:26]
    apca_id = "301500"  # mock APCA User ID
    description = f"{'PAYROLL':<12}"

    header = (
        f"0{employer_bsb.replace('-','')[:6]:>7} 01{bank_code:<3}"
        f"{'':7}{user_name}{apca_id}{description}{date_str}{'':40}"
    )
    lines.append(header[:120])

    # ── Detail Records (Type 1) ───────────────────────────────────────────
    total_credits = 0
    total_debits = 0

    for txn in transactions:
        bsb = txn.get("bsb", "062-000").replace("-", "")[:6]
        account = f"{txn.get('account_number', '00000000'):>9}"[:9]
        indicator = " "  # no withholding tax
        txn_code = "53"  # credit (pay to account)
        amount_cents = int(round(txn.get("amount", 0) * 100))
        total_credits += amount_cents
        account_name = f"{txn.get('account_name', 'Employee'):<32}"[:32]
        lodgement_ref = f"{txn.get('description', 'PAYROLL'):<18}"[:18]
        trace_bsb = employer_bsb.replace("-", "")[:6]
        trace_account = f"{employer_account:<9}"[:9]
        remitter = f"{employer_name:<16}"[:16]
        withheld = "00000000"

        detail = (
            f"1{bsb:>7}{account}{indicator}{txn_code}"
            f"{amount_cents:010d}{account_name}{lodgement_ref}"
            f"{trace_bsb:>7}{trace_account}{remitter}{withheld}"
        )
        lines.append(detail[:120])

    # Employer debit record
    total_cents = total_credits
    debit_account = f"{employer_account:>9}"[:9]
    debit_name = f"{employer_name:<32}"[:32]
    debit_ref = f"{'PAYROLL DEBIT':<18}"
    debit = (
        f"1{employer_bsb.replace('-',''):>7}{debit_account} 13"
        f"{total_cents:010d}{debit_name}{debit_ref}"
        f"{employer_bsb.replace('-',''):>7}{debit_account}"
        f"{'':16}00000000"
    )
    lines.append(debit[:120])
    total_debits = total_cents

    # ── File Total Record (Type 7) ────────────────────────────────────────
    net_balance = abs(total_credits - total_debits)
    record_count = len(transactions) + 1  # +1 for debit
    footer = (
        f"7999-999            "
        f"{total_credits:012d}{total_debits:012d}{net_balance:012d}"
        f"{' ':24}{record_count:06d}{'':40}"
    )
    lines.append(footer[:120])

    return "\r\n".join(lines)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateBatchRequest(BaseModel):
    payroll_run_id: str
    batch_type: str = "SALARY"  # SALARY or SUPERANNUATION
    pay_date: str
    payslips: List[Dict[str, Any]]
    employees: List[Dict[str, Any]]  # contains bank details
    employer_bsb: str = "062-000"
    employer_account: str = "123456789"
    employer_name: str = "ACME PTY LTD"


class SuperBatchRequest(BaseModel):
    payroll_run_id: str
    quarter: str
    due_date: str
    payslips: List[Dict[str, Any]]
    employees: List[Dict[str, Any]]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/payment-batches", status_code=201)
def create_payment_batch(req: CreateBatchRequest, db: Session = Depends(get_db),
                          user=Depends(require_role("admin", "payroll_officer"))):
    """Create ABA payment file for salary payments."""
    emp_map = {e["id"]: e for e in req.employees}

    transactions = []
    for ps in req.payslips:
        emp = emp_map.get(ps.get("employee_id"), {})
        if not emp.get("bank_account_number"):
            continue

        transactions.append({
            "bsb": emp.get("bank_bsb", "062-000"),
            "account_number": emp.get("bank_account_number"),
            "account_name": emp.get("bank_account_name", ps.get("full_name")),
            "amount": ps.get("net_pay", 0),
            "description": f"PAYROLL {ps.get('period_end', '')}",
            "employee_id": ps.get("employee_id"),
            "employee_number": ps.get("employee_number"),
            "full_name": ps.get("full_name"),
        })

    total_amount = sum(t["amount"] for t in transactions)

    aba_content = generate_aba_file(
        batch_id=str(uuid.uuid4()),
        transactions=transactions,
        employer_bsb=req.employer_bsb,
        employer_account=req.employer_account,
        employer_name=req.employer_name,
        pay_date=req.pay_date
    )

    batch = PaymentBatchDB(
        batch_type=req.batch_type,
        payroll_run_id=req.payroll_run_id,
        pay_date=req.pay_date,
        total_amount=round(total_amount, 2),
        transaction_count=len(transactions),
        aba_file_content=aba_content,
        bank_bsb=req.employer_bsb,
        bank_account=req.employer_account,
        bank_name=req.employer_name,
        created_by=user.get("email"),
    )
    db.add(batch)

    for txn in transactions:
        t = PaymentTransactionDB(
            batch_id=batch.id,
            employee_id=txn["employee_id"],
            employee_number=txn["employee_number"],
            full_name=txn["full_name"],
            bsb=txn["bsb"],
            account_number=txn["account_number"],
            account_name=txn["account_name"],
            amount=txn["amount"],
            description=txn["description"],
            transaction_type="CREDIT",
        )
        db.add(t)

    db.commit()
    db.refresh(batch)

    return {
        "batch_id": batch.id,
        "total_amount": batch.total_amount,
        "transaction_count": batch.transaction_count,
        "status": batch.status,
        "aba_available": True,
    }


@app.get("/payment-batches/{batch_id}/aba")
def download_aba_file(batch_id: str, db: Session = Depends(get_db),
                       user=Depends(require_role("admin", "payroll_officer"))):
    """Download the ABA file for a payment batch."""
    batch = db.query(PaymentBatchDB).filter(PaymentBatchDB.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if not batch.aba_file_content:
        raise HTTPException(status_code=404, detail="ABA file not generated")

    filename = f"payroll_{batch.pay_date}_{batch_id[:8]}.aba"
    return Response(
        content=batch.aba_file_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/payment-batches")
def list_batches(db: Session = Depends(get_db), user=Depends(get_current_user)):
    batches = db.query(PaymentBatchDB).order_by(PaymentBatchDB.created_at.desc()).all()
    return [
        {
            "id": b.id, "batch_type": b.batch_type, "payroll_run_id": b.payroll_run_id,
            "pay_date": b.pay_date, "total_amount": b.total_amount,
            "transaction_count": b.transaction_count, "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


@app.post("/payment-batches/{batch_id}/approve")
def approve_batch(batch_id: str, db: Session = Depends(get_db),
                  user=Depends(require_role("admin"))):
    batch = db.query(PaymentBatchDB).filter(PaymentBatchDB.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch.status = "approved"
    batch.sent_at = datetime.utcnow()
    db.commit()
    return {"message": "Payment batch approved and marked for sending", "batch_id": batch_id}


@app.post("/super-batches", status_code=201)
def create_super_batch(req: SuperBatchRequest, db: Session = Depends(get_db),
                        user=Depends(require_role("admin", "payroll_officer"))):
    """Create superannuation batch payment payload (SuperStream format)."""
    emp_map = {e["id"]: e for e in req.employees}

    contributions = []
    total_super = 0
    for ps in req.payslips:
        emp = emp_map.get(ps.get("employee_id"), {})
        super_amt = ps.get("super_guarantee", 0)
        total_super += super_amt
        contributions.append({
            "employeeId": ps.get("employee_id"),
            "employeeNumber": ps.get("employee_number"),
            "fullName": ps.get("full_name"),
            "tfn": emp.get("tfn", ""),
            "superFundName": ps.get("super_fund_name"),
            "superFundUSI": emp.get("super_fund_usi"),
            "memberNumber": ps.get("super_member_number"),
            "employerContribution": super_amt,
            "contributionType": "SG",  # Superannuation Guarantee
            "payPeriodStart": ps.get("period_start"),
            "payPeriodEnd": ps.get("period_end"),
        })

    import json
    batch = SuperBatchDB(
        payroll_run_id=req.payroll_run_id,
        quarter=req.quarter,
        due_date=req.due_date,
        total_amount=round(total_super, 2),
        employee_count=len(contributions),
        payload_json=json.dumps({"contributions": contributions}),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    return {
        "batch_id": batch.id,
        "total_super": batch.total_amount,
        "employee_count": batch.employee_count,
        "quarter": batch.quarter,
        "due_date": batch.due_date,
        "status": batch.status,
    }


@app.get("/super-batches")
def list_super_batches(db: Session = Depends(get_db), user=Depends(get_current_user)):
    batches = db.query(SuperBatchDB).order_by(SuperBatchDB.created_at.desc()).all()
    return [
        {
            "id": b.id, "payroll_run_id": b.payroll_run_id, "quarter": b.quarter,
            "due_date": b.due_date, "total_amount": b.total_amount,
            "employee_count": b.employee_count, "status": b.status,
        }
        for b in batches
    ]


@app.get("/health")
def health():
    return {"status": "ok", "service": "payments-service"}
