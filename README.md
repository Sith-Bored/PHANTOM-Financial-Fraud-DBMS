# PHANTOM — Financial Fraud Intelligence DBMS

A full-stack educational demo for transaction monitoring, fraud alert management, and SQL-backed financial analytics.

> **Academic simulation only.** Uses fictional seeded data and transparent, rule-based scoring. It is not a live banking integration or a production-grade fraud detector.

## Features
- Dark financial operations dashboard and transaction explorer
- Customer/account creation and manual transaction entry
- Rule-based fraud scanning and alert review
- Atomic simulated transfers with insufficient-funds validation
- SQLite database with relational constraints, indexes, views, and audit triggers
- Reporting endpoints and CSV export
- ER diagram, project report, quick demo guide, and viva preparation

## Run on Windows
1. Install Python 3.10 or newer.
2. Download and extract the project folder.
3. Double-click `run_phantom.bat`.
4. Open http://127.0.0.1:8080 in a browser.

No third-party Python package installation or separate database server is required.

## Layout
- `app.py` — Python HTTP API and application logic
- `web/` — frontend HTML, CSS, and JavaScript
- `database/` — schema and seed SQL
- `database/seed.sql` — fictional starter dataset; the SQLite database is created on first launch if it is missing
- `tests/` — smoke tests
- `docs/` — report, ER diagram, demo guide, and viva prep

## DBMS topics
Relational modelling, primary/foreign keys, constraints, joins, aggregate queries, indexes, views, triggers, audit trails, and atomic transactions.

## Demo walkthrough
1. Open the dashboard and inspect live database metrics.
2. Add a fictional customer and account.
3. Add a high-value transaction with the international flag enabled.
4. Run the fraud scan and review the resulting alert.
5. Change an alert status and inspect the audit trail.
6. Try a successful transfer and an insufficient-funds transfer.

See [`docs/DEMO_QUICK_GUIDE.md`](docs/DEMO_QUICK_GUIDE.md) for a presentation-ready script.

## Safety and limitations
This is a local classroom demo. It does not connect to any bank, move real funds, or use a production ML model. Do not enter real personal or financial data. Fraud scoring is rule-based and intended only to demonstrate database and application concepts.

## License
No license is currently granted. All rights are reserved by the repository owner unless a license is added.
