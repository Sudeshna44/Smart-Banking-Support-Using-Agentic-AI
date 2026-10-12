import os
import sys
from uuid import uuid4

import requests
from dotenv import load_dotenv

from banking_agent import CustomerSession, build_banking_agent, handle_customer_message


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Missing OPENROUTER_API_KEY. Copy .env.example to .env and add your key.")
        sys.exit(1)

    api_url = os.getenv("BANK_API_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        requests.get(f"{api_url}/health", timeout=3).raise_for_status()
    except requests.RequestException as error:
        print(f"Mock Banking API is not reachable at {api_url}: {error}")
        print("Start it in another terminal with: uvicorn banking_api:app --reload")
        sys.exit(1)

    customer_id = input("Mock customer ID (try CUST1001 or CUST1002): ").strip()
    if not customer_id:
        print("A mock customer ID is required to retrieve account details.")
        sys.exit(1)

    session = CustomerSession(api_url=api_url, customer_id=customer_id.upper())
    agent = build_banking_agent(session)
    thread_id = str(uuid4())

    print("\nBanking Support Agent ready. Type 'exit' to quit.")
    print("This demo uses fictional account data and the OpenRouter API.")
    while True:
        try:
            message = input("\nYou: ").strip()
            if message.casefold() in {"exit", "quit"}:
                break
            if not message:
                continue
            answer = handle_customer_message(agent, session, message, thread_id)
            print(f"\nAgent: {answer}")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break
        except requests.RequestException as error:
            print(f"\nBanking API request failed: {error}")
        except Exception as error:
            print(f"\nAgent request failed: {error}")


if __name__ == "__main__":
    main()
