"""
API Gateway - Central entry point for all frontend requests.
Routes to downstream microservices with JWT passthrough.
"""
import os
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
sys.path.append("/app/shared")
from auth import get_current_user

app = FastAPI(title="AU Payroll API Gateway", version="1.0.0",
              description="Central API Gateway for AU Payroll Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service routing table
SERVICES = {
    "/api/auth": os.getenv("EMPLOYEE_SERVICE_URL", "http://employee-service:8001"),
    "/api/employees": os.getenv("EMPLOYEE_SERVICE_URL", "http://employee-service:8001"),
    "/api/timesheets": os.getenv("TIMESHEET_SERVICE_URL", "http://timesheet-service:8002"),
    "/api/leave-requests": os.getenv("TIMESHEET_SERVICE_URL", "http://timesheet-service:8002"),
    "/api/payroll-runs": os.getenv("PAYROLL_SERVICE_URL", "http://payroll-service:8003"),
    "/api/payslips": os.getenv("PAYROLL_SERVICE_URL", "http://payroll-service:8003"),
    "/api/audit-logs": os.getenv("PAYROLL_SERVICE_URL", "http://payroll-service:8003"),
    "/api/stp": os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service:8004"),
    "/api/payg-summaries": os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service:8004"),
    "/api/payment-batches": os.getenv("PAYMENTS_SERVICE_URL", "http://payments-service:8005"),
    "/api/super-batches": os.getenv("PAYMENTS_SERVICE_URL", "http://payments-service:8005"),
    "/api/reports": os.getenv("REPORTING_SERVICE_URL", "http://reporting-service:8006"),
    "/api/orchestrate": os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8007"),
    "/api/services": os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8007"),
}

PUBLIC_PATHS = {"/api/auth/login", "/api/auth/seed-admin", "/api/health", "/docs", "/openapi.json"}


def resolve_service(path: str):
    """Find the upstream service for a given path."""
    for prefix, url in SERVICES.items():
        if path.startswith(prefix):
            return url, prefix
    return None, None


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def gateway(path: str, request: Request):
    full_path = f"/api/{path}"

    # Auth check (skip public paths)
    if full_path not in PUBLIC_PATHS and not any(full_path.startswith(p) for p in PUBLIC_PATHS):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow through - downstream services handle auth
            pass

    service_url, prefix = resolve_service(full_path)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"No service found for path: {full_path}")

    # Rewrite path: /api/employees/123 → /employees/123
    upstream_path = full_path[len("/api"):]

    # Forward query params
    query_string = str(request.url.query)
    upstream_url = f"{service_url}{upstream_path}"
    if query_string:
        upstream_url += f"?{query_string}"

    # Forward request body
    body = await request.body()

    # Forward headers (auth passthrough)
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(
                method=request.method,
                url=upstream_url,
                content=body,
                headers=forward_headers,
            )

        # Stream response back
        content_type = resp.headers.get("content-type", "application/json")
        response_headers = {}
        if "content-disposition" in resp.headers:
            response_headers["content-disposition"] = resp.headers["content-disposition"]

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=content_type,
            headers=response_headers,
        )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"detail": f"Service unavailable: {service_url}"}
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"detail": "Service timeout"}
        )


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "api-gateway", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "name": "AU Payroll Platform API Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }
