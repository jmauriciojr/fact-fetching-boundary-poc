import os

DMN_BASE_URL = os.getenv("DMN_BASE_URL", "http://localhost:8080")
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "http://localhost:8000")
DMN_MODEL_PATH = "/DiscountApproval"
GRANT_TTL_SECONDS = int(os.getenv("GRANT_TTL_SECONDS", "300"))
