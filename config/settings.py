import os

ENTRA_TENANT_ID = os.getenv("ENTRA_TENANT_ID")
ENTRA_CLIENT_ID = os.getenv("ENTRA_CLIENT_ID")
ENTRA_CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET")

AWS_REGION = os.getenv("AWS_REGION")
SAILPOINT_API_KEY = os.getenv("SAILPOINT_API_KEY")
OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/access/policy")

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

