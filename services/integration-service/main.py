"""Integration Service - orchestration layer and workflow engine."""
import os
import uuid
import httpx
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
sys.path.append("/app/shared")
from auth import get_current_user, require_role

EMPLOYEE_SVC = os.getenv("EMPLOYEE_SERVICE_URL", "http://employee-service:8001")
TIMESHEET_SVC = os.getenv("TIMESHEET_SERVICE_URL", "http://timesheet-service:8002")
PAYROLL_SVC = os.getenv("PAYROLL_SERVICE_URL", "http://payroll-service:8003")
COMPLIANCE_SVC = os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service:8004")
PAYMENTS_SVC = os.getenv("PAYMENTS_SERVICE_URL", "http://payments-service:8005")
REPORTING_SVC = os.getenv("REPORTING_SERVICE_URL", "http://reporting-service:8006")

app = FastAPI(title="Integration Service", version="1.0.0",
              description="Orchestration layer - coordinates all payroll services")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class FullPayrollRunRequest(BaseModel):
    run_name: str
    period_start: str
    period_end: str
    pay_date: str
    pay_frequency: str = "fortnightly"
    employer_bsb: str = "062-000"
    employer_account: str = "123456789"
    employer_name: str = "ACME PTY LTD"
    employer_abn: str = "12345678901"
    generate_aba: bool = True
    generate_super_batch: bool = True
    submit_stp: bool = False  # manual STP submission for safety
    employee_ids: Optional[List[str]] = None


async def orchestrate_payroll(req: FullPayrollRunRequest, token: str):
    """
    Full payroll orchestration workflow:
    1. Trigger payroll calculation
    2. Wait for completion
    3. Generate ABA payment file
    4. Generate super batch
    5. Prepare STP submission
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    results = {"steps": [], "errors": []}

    async with httpx.AsyncClient(timeout=60) as client:

        # ── Step 1: Trigger payroll run ───────────────────────────────────
        try:
            resp = await client.post(f"{PAYROLL_SVC}/payroll-runs",
                headers=headers,
                json={
                    "run_name": req.run_name,
                    "period_start": req.period_start,
                    "period_end": req.period_end,
                    "pay_date": req.pay_date,
                    "pay_frequency": req.pay_frequency,
                    "employee_ids": req.employee_ids,
                }
            )
            resp.raise_for_status()
            run_result = resp.json()
            run_id = run_result["run_id"]
            results["payroll_run_id"] = run_id
            results["steps"].append({"step": "payroll_calculation", "status": "triggered", "run_id": run_id})
        except Exception as e:
            results["errors"].append(f"Payroll run failed: {str(e)}")
            return results

        # ── Step 2: Poll until complete ───────────────────────────────────
        import asyncio
        for attempt in range(20):
            await asyncio.sleep(2)
            try:
                resp = await client.get(f"{PAYROLL_SVC}/payroll-runs/{run_id}", headers=headers)
                run_data = resp.json()
                status = run_data.get("run", {}).get("status")
                if status == "completed":
                    results["steps"].append({"step": "payroll_complete", "status": "ok",
                                              "totals": {
                                                  "gross": run_data["run"].get("total_gross"),
                                                  "net": run_data["run"].get("total_net"),
                                                  "tax": run_data["run"].get("total_tax"),
                                                  "super": run_data["run"].get("total_super"),
                                              }})
                    break
                elif status == "failed":
                    results["errors"].append("Payroll run failed during processing")
                    return results
            except Exception as e:
                pass
        else:
            results["errors"].append("Payroll run timed out")
            return results

        payslips = run_data.get("payslips", [])

        # ── Step 3: Fetch employee bank details ───────────────────────────
        try:
            emp_resp = await client.get(f"{EMPLOYEE_SVC}/employees", headers=headers)
            employees = emp_resp.json()
        except:
            employees = []

        # ── Step 4: Generate ABA file ─────────────────────────────────────
        if req.generate_aba and payslips:
            try:
                aba_resp = await client.post(f"{PAYMENTS_SVC}/payment-batches",
                    headers=headers,
                    json={
                        "payroll_run_id": run_id,
                        "batch_type": "SALARY",
                        "pay_date": req.pay_date,
                        "payslips": payslips,
                        "employees": employees,
                        "employer_bsb": req.employer_bsb,
                        "employer_account": req.employer_account,
                        "employer_name": req.employer_name,
                    }
                )
                aba_data = aba_resp.json()
                results["payment_batch_id"] = aba_data.get("batch_id")
                results["steps"].append({"step": "aba_generation", "status": "ok",
                                          "batch_id": aba_data.get("batch_id"),
                                          "total_amount": aba_data.get("total_amount")})
            except Exception as e:
                results["errors"].append(f"ABA generation failed: {str(e)}")

        # ── Step 5: Generate super batch ──────────────────────────────────
        if req.generate_super_batch and payslips:
            try:
                # Determine quarter from pay date
                pay_dt = datetime.strptime(req.pay_date, "%Y-%m-%d")
                quarter_map = {1: "Q3", 2: "Q3", 3: "Q3", 4: "Q4", 5: "Q4",
                               6: "Q4", 7: "Q1", 8: "Q1", 9: "Q1",
                               10: "Q2", 11: "Q2", 12: "Q2"}
                quarter = f"{quarter_map.get(pay_dt.month, 'Q1')} {pay_dt.year}"
                due_date = f"{pay_dt.year}-{pay_dt.month + 1:02d}-28" if pay_dt.month < 12 else f"{pay_dt.year + 1}-01-28"

                super_resp = await client.post(f"{PAYMENTS_SVC}/super-batches",
                    headers=headers,
                    json={
                        "payroll_run_id": run_id,
                        "quarter": quarter,
                        "due_date": due_date,
                        "payslips": payslips,
                        "employees": employees,
                    }
                )
                super_data = super_resp.json()
                results["super_batch_id"] = super_data.get("batch_id")
                results["steps"].append({"step": "super_batch", "status": "ok",
                                          "total_super": super_data.get("total_super")})
            except Exception as e:
                results["errors"].append(f"Super batch failed: {str(e)}")

        # ── Step 6: Prepare STP submission ────────────────────────────────
        try:
            stp_resp = await client.post(f"{COMPLIANCE_SVC}/stp/prepare",
                headers=headers,
                json={
                    "payroll_run_id": run_id,
                    "payroll_data": run_data,
                    "abn": req.employer_abn,
                    "submission_type": "PAY_EVENT",
                }
            )
            stp_data = stp_resp.json()
            results["stp_submission_id"] = stp_data.get("submission_id")
            results["steps"].append({"step": "stp_preparation", "status": stp_data.get("status"),
                                      "submission_id": stp_data.get("submission_id"),
                                      "validation_errors": stp_data.get("validation_errors", [])})
        except Exception as e:
            results["errors"].append(f"STP preparation failed: {str(e)}")

    results["status"] = "completed" if not results["errors"] else "completed_with_errors"
    return results


@app.post("/orchestrate/full-payroll-run")
async def full_payroll_run(req: FullPayrollRunRequest,
                            background_tasks: BackgroundTasks,
                            user=Depends(require_role("admin", "payroll_officer")),
                            credentials=Depends(__import__("fastapi.security", fromlist=["HTTPBearer"]).HTTPBearer())):
    """
    Orchestrate a complete payroll run across all services.
    Triggers: payroll calculation → ABA file → super batch → STP preparation
    """
    # Run synchronously so we can return results
    result = await orchestrate_payroll(req, credentials.credentials)
    return result


@app.get("/services/health")
async def services_health():
    """Check health of all downstream services."""
    services = {
        "employee-service": f"{EMPLOYEE_SVC}/health",
        "timesheet-service": f"{TIMESHEET_SVC}/health",
        "payroll-service": f"{PAYROLL_SVC}/health",
        "compliance-service": f"{COMPLIANCE_SVC}/health",
        "payments-service": f"{PAYMENTS_SVC}/health",
        "reporting-service": f"{REPORTING_SVC}/health",
    }
    results = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in services.items():
            try:
                resp = await client.get(url)
                results[name] = "ok" if resp.status_code == 200 else "degraded"
            except:
                results[name] = "unreachable"
    return {"services": results, "checked_at": datetime.utcnow().isoformat()}


@app.get("/health")
def health():
    return {"status": "ok", "service": "integration-service"}
