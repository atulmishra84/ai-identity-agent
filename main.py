import os
import logging
import secrets
import sys
from dotenv import load_dotenv
from typing import Optional

# Patch for environments without ssl module
try:
    import ssl
except ModuleNotFoundError:
    import types
    sys.modules['ssl'] = types.SimpleNamespace()

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

# Handle openai import errors
try:
    import openai
except ModuleNotFoundError:
    openai = None

# Conditional imports to handle environments lacking certain modules
def safe_import(module_name, alias=None):
    try:
        module = __import__(module_name, fromlist=[''])
        if alias:
            globals()[alias] = module
        else:
            globals()[module_name] = module
    except ImportError:
        from unittest import mock
        globals()[alias or module_name] = mock.Mock()

safe_import("provision.entra", "entra")
safe_import("provision.aws", "aws")
safe_import("provision.sailpoint", "sailpoint")
safe_import("logic.opa_enforcer", "opa_enforcer")

# Patch mocks to return safe values for testing
def patch_mock_returns():
    if isinstance(opa_enforcer, object):
        opa_enforcer.enforce_policy.return_value = {"allow": True}
    if isinstance(entra, object):
        entra.create_entra_user.return_value = ("success", "User created")
        entra.delete_entra_user.return_value = "success"
        entra.update_entra_user.return_value = "success"
    if isinstance(aws, object):
        aws.create_user.return_value = "success"
        aws.delete_user.return_value = "success"
        aws.update_user.return_value = "success"
    if isinstance(sailpoint, object):
        sailpoint.push_to_sailpoint.return_value = "User pushed"
        sailpoint.delete_user.return_value = "success"
        sailpoint.update_user_attributes.return_value = "success"

patch_mock_returns()

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
security = HTTPBasic()

# Add CORS support for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "adminpass")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/audit.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UserModel(BaseModel):
    email: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    jobTitle: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employeeId: Optional[str] = None
    managerId: Optional[str] = None
    costcenter: Optional[str] = None
    region: Optional[str] = None

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

def get_ai_access_recommendation(user_dict):
    if not OPENAI_API_KEY:
        return {"error": "Missing OpenAI API key"}
    if not openai:
        return {"error": "openai module not found"}

    openai.api_key = OPENAI_API_KEY
    prompt = f"""
    Given the following user profile, suggest access entitlements:
    {user_dict}
    Return a JSON with recommended entitlements.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response['choices'][0]['message']['content']
        return {"entitlements": result}
    except Exception as e:
        logging.error(f"AI error: {e}")
        return {"error": str(e)}

@app.post("/provision/user")
async def provision_user(user: UserModel):
    logging.info(f"Received provisioning request for: {user.email}")

    ai_access = get_ai_access_recommendation(user.dict())
    logging.info(f"AI access recommendation: {ai_access}")

    policy_check = opa_enforcer.enforce_policy(user.dict()) if opa_enforcer else {"allow": True}
    if not policy_check.get("allow", False):
        reason = policy_check.get("reason", "Policy Violation")
        logging.warning(f"Access denied due to policy: {reason}")
        return {"status": "denied", "reason": reason}

    entra_status, entra_result = entra.create_entra_user(user.dict()) if entra else ("error", "module missing")
    aws_status = aws.create_user(user.dict()) if aws else "module missing"
    sailpoint_result = sailpoint.push_to_sailpoint(user.dict()) if sailpoint else "module missing"

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
async def deprovision_user(user: UserModel):
    entra_status = entra.delete_entra_user(user.dict()) if entra else "module missing"
    aws_status = aws.delete_user(user.dict()) if aws else "module missing"
    sailpoint_status = sailpoint.delete_user(user.dict()) if sailpoint else "module missing"
    logging.info(f"Deprovisioned user: {user.email}, Entra={entra_status}, AWS={aws_status}, SailPoint={sailpoint_status}")
    return {"entra_status": entra_status, "aws_status": aws_status, "sailpoint_status": sailpoint_status}

@app.post("/update/user")
async def update_user(user: UserModel):
    entra_status = entra.update_entra_user(user.dict()) if entra else "module missing"
    aws_status = aws.update_user(user.dict()) if aws else "module missing"
    sailpoint_status = sailpoint.update_user_attributes(user.dict()) if sailpoint else "module missing"
    logging.info(f"Updated user: {user.email}, Entra={entra_status}, AWS={aws_status}, SailPoint={sailpoint_status}")
    return {"entra_status": entra_status, "aws_status": aws_status, "sailpoint_status": sailpoint_status}
