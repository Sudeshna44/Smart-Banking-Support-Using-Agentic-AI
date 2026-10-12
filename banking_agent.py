import json
import os
from dataclasses import dataclass

import requests
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver


@dataclass
class CustomerSession:
    api_url: str
    customer_id: str
    pending_application: dict | None = None
    confirmation_granted: bool = False


def _post_json(api_url: str, path: str, payload: dict | None = None) -> dict:
    response = requests.post(f"{api_url}{path}", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def _get_json(api_url: str, path: str) -> dict:
    response = requests.get(f"{api_url}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def _is_explicit_confirmation(message: str) -> bool:
    return message.strip().casefold() == "confirm"


def build_banking_agent(session: CustomerSession):
    @tool
    def calculate_loan_emi(loan_amount: float, term_months: int) -> str:
        """Calculate a personal-loan EMI using the mock bank's disclosed product rate."""
        result = _post_json(
            session.api_url,
            "/tools/calculate-emi",
            {"loan_amount": loan_amount, "term_months": term_months},
        )
        return json.dumps(result)

    @tool
    def check_loan_eligibility(
        loan_amount: float,
        term_months: int,
        monthly_salary: float,
        existing_monthly_emi: float,
    ) -> str:
        """Check mock loan eligibility using monthly salary and existing EMI obligations."""
        result = _post_json(
            session.api_url,
            "/tools/check-eligibility",
            {
                "loan_amount": loan_amount,
                "term_months": term_months,
                "monthly_salary": monthly_salary,
                "existing_monthly_emi": existing_monthly_emi,
            },
        )
        if result["eligible"]:
            session.pending_application = {
                "loan_amount": loan_amount,
                "term_months": term_months,
                "monthly_salary": monthly_salary,
                "existing_monthly_emi": existing_monthly_emi,
            }
        else:
            session.pending_application = None
        session.confirmation_granted = False
        return json.dumps(result)

    @tool
    def retrieve_account_details() -> str:
        """Retrieve mock account details for the authenticated demo customer."""
        return json.dumps(
            _get_json(session.api_url, f"/accounts/{session.customer_id}")
        )

    @tool
    def submit_loan_application() -> str:
        """Submit the eligible loan application only after the customer explicitly types CONFIRM."""
        if session.pending_application is None:
            return "Submission blocked: there is no currently eligible pending application."
        if not session.confirmation_granted:
            return (
                "Submission blocked: explicit customer confirmation is required. "
                "Show the proposed terms and ask the customer to type CONFIRM."
            )

        application = _post_json(
            session.api_url,
            "/applications",
            {
                "customer_id": session.customer_id,
                **session.pending_application,
                "customer_confirmation": True,
            },
        )
        session.pending_application = None
        session.confirmation_granted = False
        return json.dumps(application)

    tools = [
        calculate_loan_emi,
        check_loan_eligibility,
        retrieve_account_details,
        submit_loan_application,
    ]
    model = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"),
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
    )
    system_prompt = f"""
You are one friendly banking support agent using fictional local demo data.
The current mock customer ID is {session.customer_id!r}; use this ID with the account
tool when the customer asks for their account details. It is acceptable to show only
the masked account number. Never invent account data, tool results, or application IDs.

For requests involving a loan, gather missing amount, term, monthly salary, or current
monthly EMI by asking the customer. The mock personal-loan rate is
{os.getenv("BANK_ANNUAL_INTEREST_RATE", "12")}% per year. Use tools to calculate the
EMI and check eligibility; do not estimate these values yourself. Retrieve account
details when requested. Use tool outputs to decide what to do next.

If ineligible, explain the result and do not submit. If eligible, explain the EMI,
assumed rate, FOIR, and eligibility. Ask the customer to type exactly CONFIRM before
submission. Never call the submission tool until the customer has typed exactly
CONFIRM in a later message. Do not treat an earlier request to "help submit" as
confirmation. After submission, report the application ID and status returned by the
tool. Summarize EMI, eligibility, and application status in the final response.
Clearly state this is a mock demo, not a credit decision.
"""
    return create_agent(
        model,
        tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )


def handle_customer_message(agent, session: CustomerSession, message: str, thread_id: str) -> str:
    if session.pending_application is not None and _is_explicit_confirmation(message):
        session.confirmation_granted = True
    else:
        session.confirmation_granted = False

    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    answer = result["messages"][-1].content
    if isinstance(answer, str):
        return answer
    return json.dumps(answer, ensure_ascii=False)
