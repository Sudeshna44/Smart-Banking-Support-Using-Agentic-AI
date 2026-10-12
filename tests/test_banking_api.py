import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from banking_api import CHAT_SESSIONS, app, calculate_emi


class BankingApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {"BANK_DB_PATH": os.path.join(self.temp_dir.name, "test.sqlite3")},
        )
        self.env.start()
        CHAT_SESSIONS.clear()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()

    def test_emi_uses_expected_amortization(self):
        self.assertEqual(calculate_emi(500000, 12, 36), 16607.15)

    def test_account_lookup_returns_masked_demo_account(self):
        response = self.client.get("/accounts/CUST1001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_number"], "XXXXXX4821")

    def test_eligibility_includes_existing_emi(self):
        response = self.client.post(
            "/tools/check-eligibility",
            json={
                "loan_amount": 500000,
                "term_months": 36,
                "monthly_salary": 60000,
                "existing_monthly_emi": 5000,
            },
        )
        result = response.json()
        self.assertTrue(result["eligible"])
        self.assertEqual(result["proposed_monthly_emi"], 16607.15)
        self.assertEqual(result["foir_percent"], 36.01)

    def test_application_requires_explicit_confirmation(self):
        response = self.client.post(
            "/applications",
            json={
                "customer_id": "CUST1001",
                "loan_amount": 500000,
                "term_months": 36,
                "monthly_salary": 60000,
                "existing_monthly_emi": 5000,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_application_submits_only_when_confirmed_and_eligible(self):
        response = self.client.post(
            "/applications",
            json={
                "customer_id": "CUST1001",
                "loan_amount": 500000,
                "term_months": 36,
                "monthly_salary": 60000,
                "existing_monthly_emi": 5000,
                "customer_confirmation": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["application_id"].startswith("LOAN-"))

    def test_application_rejects_ineligible_customer_even_when_confirmed(self):
        response = self.client.post(
            "/applications",
            json={
                "customer_id": "CUST1001",
                "loan_amount": 500000,
                "term_months": 36,
                "monthly_salary": 20000,
                "existing_monthly_emi": 5000,
                "customer_confirmation": True,
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_website_and_chat_assets_are_served(self):
        page = self.client.get("/")
        script = self.client.get("/static/app.js")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Banking support", page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("chat/sessions", script.text)

    def test_chat_session_rejects_unknown_demo_customer(self):
        response = self.client.post(
            "/chat/sessions", json={"customer_id": "UNKNOWN"}
        )
        self.assertEqual(response.status_code, 404)

    def test_chat_session_and_message_route_through_agent(self):
        from banking_agent import CustomerSession

        mock_session = CustomerSession(
            api_url="http://127.0.0.1:8000", customer_id="CUST1001"
        )
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            with patch("banking_agent.build_banking_agent", return_value=object()):
                created = self.client.post(
                    "/chat/sessions", json={"customer_id": "CUST1001"}
                )
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["session_id"]
        self.assertEqual(created.json()["customer_name"], "Aarav Sharma")

        agent = CHAT_SESSIONS[session_id][0]
        CHAT_SESSIONS[session_id] = (agent, mock_session)
        with patch(
            "banking_agent.handle_customer_message", return_value="Test reply"
        ) as handle_message:
            response = self.client.post(
                f"/chat/sessions/{session_id}/messages",
                json={"message": "Hello"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "Test reply"})
        handle_message.assert_called_once_with(agent, mock_session, "Hello", session_id)


if __name__ == "__main__":
    unittest.main()
