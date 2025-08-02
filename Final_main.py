import os
import logging
import secrets
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Conditional imports to handle environments lacking certain modules
def safe_import(module_name, alias=None):
    try:
        module = __import__(module_name)
        if alias:
            globals()[alias] = module
        else:
            globals()[module_name] = module
    except ImportError:
        print(f"Warning: Could not import {module_name}. Some functionality may be limited.")

safe_import("provision.entra", "entra")
safe_import("provision.aws", "aws")
safe_import("provision.sailpoint", "sailpoint")
safe_import("logic.ai_recommender", "ai_recommender")
safe_import("logic.opa_enforcer", "opa_enforcer")

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
security = HTTPBasic()

DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "adminpass")

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/audit.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, DASHBOARD_USER)
    correct_password = secrets.compare_digest(credentials.password, DASHBOARD_PASS)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(credentials: HTTPBasicCredentials = Depends(authenticate)):
    try:
        with open("logs/audit.log", "r") as f:
            logs = f.readlines()
        logs.reverse()
        formatted_logs = ''.join(f"<div>{log.strip()}</div>" for log in logs)
        return f"""
            <html>
                <head><title>Audit Log Dashboard</title></head>
                <body>
                    <h2>Audit Log</h2>
                    <form method='get'>
                        <input type='text' name='q' placeholder='Search logs...' />
                        <input type='submit' value='Search' />
                    </form>
                    <div style='font-family: monospace; white-space: pre-wrap;'>{formatted_logs}</div>
                </body>
            </html>
        """
    except FileNotFoundError:
        return "<html><body><h2>No logs available yet.</h2></body></html>"

@app.post("/provision/user")
async def provision_user(request: Request):
    user = await request.json()
    logging.info(f"Received provisioning request for: {user.get('email', 'unknown')}")

    ai_access = ai_recommender.get_access_recommendation(user) if ai_recommender else {}
    logging.info(f"AI access recommendation: {ai_access}")

    policy_check = opa_enforcer.enforce_policy(user) if opa_enforcer else {"allow": True}
    if not policy_check.get("allow", False):
        reason = policy_check.get("reason", "Policy Violation")
        logging.warning(f"Access denied due to policy: {reason}")
        return {"status": "denied", "reason": reason}

    entra_status, entra_result = entra.create_entra_user(user) if entra else ("error", "module missing")
    aws_status = aws.create_user(user) if aws else "module missing"
    sailpoint_result = sailpoint.push_to_sailpoint(user) if sailpoint else "module missing"

    logging.info(f"Provisioning complete: Entra={entra_status}, AWS={aws_status}, SailPoint={sailpoint_result}")

    return {
        "entra_status": entra_status,
        "entra_result": entra_result,
        "aws_status": aws_status,
        "ai_access": ai_access,
        "policy_check": policy_check,
        "sailpoint_result": sailpoint_result
    }

@app.post("/deprovision/user")
async def deprovision_user(request: Request):
    user = await request.json()
    entra_status = entra.delete_entra_user(user) if entra else "module missing"
    aws_status = aws.delete_user(user) if aws else "module missing"
    sailpoint_status = sailpoint.delete_user(user) if sailpoint else "module missing"
    logging.info(f"Deprovisioned user: {user.get('email', 'unknown')}, Entra={entra_status}, AWS={aws_status}, SailPoint={sailpoint_status}")
    return {"entra_status": entra_status, "aws_status": aws_status, "sailpoint_status": sailpoint_status}

@app.post("/update/user")
async def update_user(request: Request):
    user = await request.json()
    entra_status = entra.update_entra_user(user) if entra else "module missing"
    aws_status = aws.update_user(user) if aws else "module missing"
    sailpoint_status = sailpoint.update_user_attributes(user) if sailpoint else "module missing"
    logging.info(f"Updated user: {user.get('email', 'unknown')}, Entra={entra_status}, AWS={aws_status}, SailPoint={sailpoint_status}")
    return {"entra_status": entra_status, "aws_status": aws_status, "sailpoint_status": sailpoint_status}
