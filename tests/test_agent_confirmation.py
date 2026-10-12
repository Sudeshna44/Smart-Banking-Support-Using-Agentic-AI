import unittest
from types import SimpleNamespace

from banking_agent import CustomerSession, handle_customer_message


class StubAgent:
    def invoke(self, state, config):
        return {"messages": [SimpleNamespace(content="Demo response")]}


class AgentConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.agent = StubAgent()
        self.session = CustomerSession(
            api_url="http://127.0.0.1:8000",
            customer_id="CUST1001",
            pending_application={"loan_amount": 500000},
        )

    def test_only_exact_confirmation_grants_submission_for_that_turn(self):
        handle_customer_message(self.agent, self.session, "yes", "test-thread")
        self.assertFalse(self.session.confirmation_granted)

        handle_customer_message(self.agent, self.session, "CONFIRM", "test-thread")
        self.assertTrue(self.session.confirmation_granted)

        handle_customer_message(self.agent, self.session, "actually, wait", "test-thread")
        self.assertFalse(self.session.confirmation_granted)

    def test_confirmation_without_pending_application_does_not_grant_submission(self):
        self.session.pending_application = None
        handle_customer_message(self.agent, self.session, "CONFIRM", "test-thread")
        self.assertFalse(self.session.confirmation_granted)


if __name__ == "__main__":
    unittest.main()
