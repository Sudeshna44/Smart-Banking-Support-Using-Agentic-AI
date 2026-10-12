# Smart Banking Support Agent

A local training demo with **one LangChain agent**, four banking tools, a FastAPI
mock bank API, and SQLite-backed loan applications. OpenRouter supplies the
language model; you provide your own OpenRouter API key.

All customer records are fictional. The mock eligibility policy approves a loan
when existing and proposed monthly EMIs together are no more than 50% of monthly
salary. The demo personal-loan interest rate defaults to 12% annually. This is
not a real bank credit decision.

## Setup

1. Use Python 3.10 or newer and install dependencies:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add your OpenRouter key:

   ```powershell
   Copy-Item .env.example .env
   ```

   Set `OPENROUTER_API_KEY` in `.env`. You may also change
   `OPENROUTER_MODEL` to another model available to your OpenRouter account.

3. Start the app (API and website) from the project folder:

   ```powershell
   .venv\Scripts\Activate.ps1
   uvicorn banking_api:app --reload
   ```

4. Open **<http://127.0.0.1:8000>** in your browser. Choose one of the fictional
   demo profiles and start chatting. To open the interactive API documentation,
   visit **<http://127.0.0.1:8000/docs>**.

   Example request:

   > I want to apply for a personal loan of ₹5,00,000 for three years. My monthly
   > salary is ₹60,000, and I already pay ₹5,000 as an EMI for another loan.
   > Calculate my monthly EMI, check my loan eligibility, retrieve my account
   > details, and help me submit a loan application if I qualify.

   If eligible, review the terms and type exactly `CONFIRM` in a separate
   message to authorize submission. The agent cannot override this confirmation
   gate; the API also rejects submissions without confirmation or eligibility.

The browser chat asks for a demo customer profile at startup. During the
conversation, the agent asks for required loan details if they are absent. Its
tools call the local API for EMI calculation, eligibility, account lookup, and
application submission. Successful applications are stored in
`bank_demo.sqlite3` (or `BANK_DB_PATH`). You can still use the terminal chat
with `python main.py` if preferred.

## API and tests

FastAPI Swagger documentation is available at <http://127.0.0.1:8000/docs>.
Endpoints:

- `GET /accounts/{customer_id}`
- `POST /tools/calculate-emi`
- `POST /tools/check-eligibility`
- `POST /applications`

Run tests with:

```powershell
python -m unittest discover -s tests -v
```
