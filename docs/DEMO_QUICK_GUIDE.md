# PHANTOM — Live Demo Quick Guide

## What works in the application now

- **Overview dashboard:** SQL-backed totals, six-month transaction activity, category totals, risk distribution, latest alerts, and latest audit events.
- **Transaction explorer:** Search by merchant/customer/reference, filter by risk/status, and export matching records to CSV.
- **Manual transaction entry:** Add a transaction against an existing account. The record is stored in SQLite and audited.
- **Customer onboarding:** Create a customer and linked account using one form. Customer and account insert together or roll back together; duplicate email is rejected.
- **Rule-based fraud scan:** Re-evaluates transactions, updates scores, and creates non-duplicate alerts with rule names and explanations.
- **Alert operations:** Search/filter, move alerts to Investigating, Resolve, False Positive, or reopen. Each decision is logged.
- **Transfer simulation:** Updates two balances, transaction ledger, and audit event atomically. A debit that would overdraw the source is rejected without a partial balance update.
- **Accounts and SQL insights:** SQL view-derived balance, counts and alert statistics, category/alert aggregates, and example queries.
- **Audit trail:** Shows trigger-logged transaction/alert creation plus explicit customer, account, scan, transfer and analyst-action events.

## Strongest 3-minute demonstration

### 1. Start

Double-click `run_phantom.bat`, keep the terminal open, and visit `http://127.0.0.1:8080`.

### 2. Create a customer + account

Open **Accounts** → **Add customer / account** and enter:

- Full name: `Aanya Kapoor`
- Email: `aanya.kapoor@example.test`
- Phone: `+91-90000-12001`
- Risk tier: `MEDIUM`
- Account type: `SAVINGS`
- Opening balance: `200000`
- Country: `IN`

Save. PHANTOM generates an account ID. Mention that the customer and account are separate normalized rows linked by a foreign key and are created together in a database transaction.

### 3. Create a risky transaction

Open **Transactions** → **Add transaction**. Select Aanya's newly created account and enter:

- Merchant / description: `Nova Electronics`
- Category: `E-commerce`
- Amount: `125000`
- Type: `Payment`
- Status: `Completed`
- Channel: `Online`
- Location: `Singapore, SG`
- IP: `192.0.2.77` (documentation/test address)
- Device ID: `PHANTOM-DEMO-77`
- International: **checked**

Save. Explain this is a new row stored by the backend, not hard-coded dashboard content. Its initial score is 5 until a scan is run.

### 4. Generate and investigate the alert

Open **Fraud alerts** → **Run threat scan**. For this example, the high-value rule adds 65 points and cross-border adds 35, giving a capped score of 100. Confirm the resulting Critical alert for `Nova Electronics`, then move it to **Investigating**.

### 5. Prove traceability

Open **Audit trail**. Show the events for customer/account creation, transaction creation, scan, alert creation, and alert status change. The data change propagates through actual database-backed queries.

### Optional: show transaction safety

Use **Simulate transfer** to move ₹500 between two active accounts, then try an amount higher than the source's available balance. The second attempt should be rejected; both the source and destination balances must remain unchanged for the failed request.

## What to say if asked “is this just a UI?”

“No. The frontend calls a local Python API. The API executes parameterized SQL against SQLite. User-created customer, account, transaction and alert records are stored persistently. SQL views power account summaries; triggers create audit events; and transfers use a real database transaction with rollback on failure. The dashboard and reports recalculate from database records.”

## Current honest limitations

- Data and balances are fictional and local. No bank/payment network is connected.
- Fraud scoring uses understandable heuristic rules, not AI/ML and not a certified fraud model.
- Customer/account and transaction creation are available; full edit/delete workflows and CSV import are future improvements.
- No authentication/roles are implemented; keep the server bound to localhost for this classroom demo.

## Reset

Stop the app with Ctrl+C, delete `data/phantom.db` and its optional `-wal` / `-shm` sidecars, then start `run_phantom.bat` again. The starter schema and seed dataset are recreated.
