"""Employee Service - manages employee master data."""
import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Enum as SAEnum, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role, hash_password, verify_password, create_access_token
from models import EmploymentType, PayFrequency, UserRole

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://payroll:payroll123@postgres:5432/employee_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Employee Service", version="1.0.0", description="Manages employee master data for AU Payroll")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Database Models ──────────────────────────────────────────────────────────

class EmployeeDB(Base):
    __tablename__ = "employees"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_number = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    tfn = Column(String)  # Tax File Number (encrypted in production)
    employment_type = Column(SAEnum(EmploymentType), nullable=False)
    pay_frequency = Column(SAEnum(PayFrequency), default=PayFrequency.FORTNIGHTLY)
    annual_salary = Column(Float, nullable=False)
    hourly_rate = Column(Float)
    super_fund_name = Column(String)
    super_fund_usi = Column(String)
    super_member_number = Column(String)
    bank_bsb = Column(String)
    bank_account_number = Column(String)
    bank_account_name = Column(String)
    start_date = Column(String, nullable=False)
    end_date = Column(String)
    is_active = Column(Boolean, default=True)
    tax_free_threshold = Column(Boolean, default=True)
    residency_status = Column(String, default="resident")
    address_line1 = Column(String)
    address_suburb = Column(String)
    address_state = Column(String)
    address_postcode = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserDB(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="employee")
    employee_id = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    employee_number: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    tfn: Optional[str] = None
    employment_type: EmploymentType
    pay_frequency: PayFrequency = PayFrequency.FORTNIGHTLY
    annual_salary: float
    hourly_rate: Optional[float] = None
    super_fund_name: Optional[str] = "AustralianSuper"
    super_fund_usi: Optional[str] = None
    super_member_number: Optional[str] = None
    bank_bsb: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_account_name: Optional[str] = None
    start_date: str
    tax_free_threshold: bool = True
    residency_status: str = "resident"
    address_line1: Optional[str] = None
    address_suburb: Optional[str] = None
    address_state: Optional[str] = None
    address_postcode: Optional[str] = None


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    pay_frequency: Optional[PayFrequency] = None
    annual_salary: Optional[float] = None
    hourly_rate: Optional[float] = None
    super_fund_name: Optional[str] = None
    super_member_number: Optional[str] = None
    bank_bsb: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_account_name: Optional[str] = None
    is_active: Optional[bool] = None


class EmployeeResponse(BaseModel):
    id: str
    employee_number: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    employment_type: EmploymentType
    pay_frequency: PayFrequency
    annual_salary: float
    hourly_rate: Optional[float]
    super_fund_name: Optional[str]
    super_member_number: Optional[str]
    bank_bsb: Optional[str]
    bank_account_number: Optional[str]
    bank_account_name: Optional[str]
    start_date: str
    is_active: bool
    tax_free_threshold: bool
    residency_status: str

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.EMPLOYEE
    employee_id: Optional[str] = None


# ── DB Dependency ─────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "user_id": user.id}


@app.post("/auth/register", dependencies=[Depends(require_role("admin"))])
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserDB(email=req.email, hashed_password=hash_password(req.password),
                  role=req.role, employee_id=req.employee_id)
    db.add(user)
    db.commit()
    return {"message": "User created", "user_id": user.id}


@app.post("/auth/seed-admin")
def seed_admin(db: Session = Depends(get_db)):
    """Seed initial admin user - only works if no admin exists."""
    existing = db.query(UserDB).filter(UserDB.role == "admin").first()
    if existing:
        return {"message": "Admin already exists"}
    admin = UserDB(email="admin@payroll.com.au", hashed_password=hash_password("Admin1234!"), role="admin")
    db.add(admin)
    db.commit()
    return {"message": "Admin seeded", "email": "admin@payroll.com.au", "password": "Admin1234!"}


# ── Employee Routes ───────────────────────────────────────────────────────────

@app.post("/employees", response_model=EmployeeResponse, status_code=201)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db),
                    user=Depends(require_role("admin", "payroll_officer"))):
    existing = db.query(EmployeeDB).filter(
        (EmployeeDB.email == data.email) | (EmployeeDB.employee_number == data.employee_number)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee number or email already exists")
    emp = EmployeeDB(**data.dict())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@app.get("/employees", response_model=List[EmployeeResponse])
def list_employees(active_only: bool = True, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    q = db.query(EmployeeDB)
    if active_only:
        q = q.filter(EmployeeDB.is_active == True)
    return q.all()


@app.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    emp = db.query(EmployeeDB).filter(EmployeeDB.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@app.patch("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: str, data: EmployeeUpdate, db: Session = Depends(get_db),
                    user=Depends(require_role("admin", "payroll_officer"))):
    emp = db.query(EmployeeDB).filter(EmployeeDB.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in data.dict(exclude_none=True).items():
        setattr(emp, field, value)
    emp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(emp)
    return emp


@app.delete("/employees/{employee_id}")
def deactivate_employee(employee_id: str, db: Session = Depends(get_db),
                        user=Depends(require_role("admin"))):
    emp = db.query(EmployeeDB).filter(EmployeeDB.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.is_active = False
    emp.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Employee deactivated"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "employee-service"}
