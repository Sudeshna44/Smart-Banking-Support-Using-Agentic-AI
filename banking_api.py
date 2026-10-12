import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


load_dotenv()

ANNUAL_INTEREST_RATE = float(os.getenv("BANK_ANNUAL_INTEREST_RATE", "12"))
MAX_FOIR_PERCENT = 50.0

# These are fictional customer records for local demonstrations only.
MOCK_ACCOUNTS = {
    "CUST1001": {
        "customer_id": "CUST1001",
        "name": "Aarav Sharma",
        "account_number": "XXXXXX4821",
        "account_type": "Savings",
        "available_balance": 125000.00,
    },
    "CUST1002": {
        "customer_id": "CUST1002",
        "name": "Diya Patel",
        "account_number": "XXXXXX7390",
        "account_type": "Savings",
        "available_balance": 84250.50,
    },
}

app = FastAPI(
    title="Mock Banking Support API",
    description="Local demo API with fictional customer and loan data.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

CHAT_SESSIONS: dict[str, tuple[object, object]] = {}


class EmiRequest(BaseModel):
    loan_amount: float = Field(gt=0)
    term_months: int = Field(gt=0, le=360)


class EligibilityRequest(EmiRequest):
    monthly_salary: float = Field(gt=0)
    existing_monthly_emi: float = Field(ge=0)


class LoanApplicationRequest(EligibilityRequest):
    customer_id: str
    customer_confirmation: Literal[True]


class ChatSessionRequest(BaseModel):
    customer_id: str


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def calculate_emi(loan_amount: float, annual_interest_rate: float, term_months: int) -> float:
    monthly_rate = annual_interest_rate / 12 / 100
    if monthly_rate == 0:
        return round(loan_amount / term_months, 2)
    factor = (1 + monthly_rate) ** term_months
    return round(loan_amount * monthly_rate * factor / (factor - 1), 2)


def assess_eligibility(
    loan_amount: float,
    term_months: int,
    monthly_salary: float,
    existing_monthly_emi: float,
) -> dict:
    proposed_emi = calculate_emi(loan_amount, ANNUAL_INTEREST_RATE, term_months)
    total_monthly_emi = existing_monthly_emi + proposed_emi
    foir_percent = round(total_monthly_emi / monthly_salary * 100, 2)
    eligible = foir_percent <= MAX_FOIR_PERCENT
    return {
        "eligible": eligible,
        "proposed_monthly_emi": proposed_emi,
        "existing_monthly_emi": round(existing_monthly_emi, 2),
        "total_monthly_emi": round(total_monthly_emi, 2),
        "monthly_salary": round(monthly_salary, 2),
        "foir_percent": foir_percent,
        "foir_limit_percent": MAX_FOIR_PERCENT,
        "annual_interest_rate_percent": ANNUAL_INTEREST_RATE,
        "reasons": (
            ["Monthly EMI obligations are within the mock policy limit."]
            if eligible
            else ["Total monthly EMI obligations exceed the mock policy limit."]
        ),
        "disclaimer": "Demo estimate only; this is not a bank credit decision.",
    }


def _database_path() -> Path:
    return Path(os.getenv("BANK_DB_PATH", "bank_demo.sqlite3"))


def _save_application(application: dict) -> None:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS loan_applications (
                    application_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    loan_amount REAL NOT NULL,
                    term_months INTEGER NOT NULL,
                    monthly_salary REAL NOT NULL,
                    existing_monthly_emi REAL NOT NULL,
                    proposed_monthly_emi REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO loan_applications (
                    application_id, customer_id, loan_amount, term_months,
                    monthly_salary, existing_monthly_emi, proposed_monthly_emi,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application["application_id"],
                    application["customer_id"],
                    application["loan_amount"],
                    application["term_months"],
                    application["monthly_salary"],
                    application["existing_monthly_emi"],
                    application["proposed_monthly_emi"],
                    application["status"],
                    application["created_at"],
                ),
            )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def chat_website() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/chat/sessions")
def create_chat_session(request: ChatSessionRequest) -> dict:
    customer_id = request.customer_id.strip().upper()
    if customer_id not in MOCK_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Choose CUST1001 or CUST1002.")
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is missing. Add it to the local .env file and restart the server.",
        )

    from banking_agent import CustomerSession, build_banking_agent

    session = CustomerSession(
        api_url=os.getenv("BANK_API_URL", "http://127.0.0.1:8000").rstrip("/"),
        customer_id=customer_id,
    )
    try:
        agent = build_banking_agent(session)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not initialize the banking agent: {type(error).__name__}.",
        ) from error

    session_id = str(uuid4())
    CHAT_SESSIONS[session_id] = (agent, session)
    return {"session_id": session_id, "customer_name": MOCK_ACCOUNTS[customer_id]["name"]}


@app.post("/chat/sessions/{session_id}/messages")
def send_chat_message(session_id: str, request: ChatMessageRequest) -> dict:
    session_data = CHAT_SESSIONS.get(session_id)
    if session_data is None:
        raise HTTPException(status_code=404, detail="Chat session not found. Start a new chat.")

    from banking_agent import handle_customer_message

    agent, session = session_data
    try:
        answer = handle_customer_message(agent, session, request.message.strip(), session_id)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Agent request failed: {type(error).__name__}. Check the API key, model, and connection.",
        ) from error
    return {"reply": answer}


@app.get("/accounts/{customer_id}")
def get_account(customer_id: str) -> dict:
    account = MOCK_ACCOUNTS.get(customer_id.upper())
    if account is None:
        raise HTTPException(status_code=404, detail="Mock customer ID not found.")
    return account


@app.post("/tools/calculate-emi")
def calculate_emi_endpoint(request: EmiRequest) -> dict:
    return {
        "loan_amount": request.loan_amount,
        "term_months": request.term_months,
        "annual_interest_rate_percent": ANNUAL_INTEREST_RATE,
        "monthly_emi": calculate_emi(
            request.loan_amount, ANNUAL_INTEREST_RATE, request.term_months
        ),
        "disclaimer": "Demo estimate only; actual bank rates and fees may differ.",
    }


@app.post("/tools/check-eligibility")
def check_eligibility_endpoint(request: EligibilityRequest) -> dict:
    return assess_eligibility(
        request.loan_amount,
        request.term_months,
        request.monthly_salary,
        request.existing_monthly_emi,
    )


@app.post("/applications", status_code=201)
def submit_application(request: LoanApplicationRequest) -> dict:
    customer_id = request.customer_id.upper()
    if customer_id not in MOCK_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Mock customer ID not found.")

    eligibility = assess_eligibility(
        request.loan_amount,
        request.term_months,
        request.monthly_salary,
        request.existing_monthly_emi,
    )
    if not eligibility["eligible"]:
        raise HTTPException(status_code=409, detail="Customer does not meet mock eligibility.")

    application = {
        "application_id": f"LOAN-{uuid4().hex[:10].upper()}",
        "customer_id": customer_id,
        "loan_amount": request.loan_amount,
        "term_months": request.term_months,
        "monthly_salary": request.monthly_salary,
        "existing_monthly_emi": request.existing_monthly_emi,
        "proposed_monthly_emi": eligibility["proposed_monthly_emi"],
        "status": "submitted",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_application(application)
    return application
