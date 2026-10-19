# PHANTOM — DBMS Viva Preparation

This sheet is tailored to the included implementation. Use your own words in the viva and be ready to point to the actual table, view, trigger, endpoint, or workflow being discussed.

## 45-second project explanation

PHANTOM is a local financial fraud intelligence application built to demonstrate DBMS concepts in a working system. The frontend is made with HTML, CSS, and JavaScript; Python's standard-library HTTP server exposes the API; SQLite stores customers, accounts, transactions, fraud alerts, and audit logs. The dashboard uses real SQL aggregation, analysts can add customers/accounts and transactions through validated UI forms, the scan endpoint applies explainable rules to those transaction records, and alert actions update the database and append audit events. The simulated transfer demonstrates atomicity by debiting and crediting two accounts in a single database transaction with rollback on failure. All data is fictional and no real bank system is connected.

## Key facts to memorize

- **Database:** SQLite, accessed with Python's built-in `sqlite3` module.
- **Core tables:** `customers`, `accounts`, `transactions`, `fraud_alerts`, `audit_logs`.
- **Views:** `v_account_summary`, `v_open_alerts`.
- **Triggers:** `trg_transaction_audit`, `trg_alert_audit`, `trg_prevent_negative_balance`.
- **Main relationships:** customer 1-to-many accounts; account 1-to-many transactions; transaction 1-to-zero-or-one alert; account 1-to-many alerts.
- **Demo data:** 18 customers, 24 accounts, 94 transactions, 15 seeded alerts (counts can change after using the app).
- **Transfer safety:** `BEGIN IMMEDIATE`, conditional debit, destination credit, transaction insert, audit insert, commit; rollback on any exception.
- **User-entered data:** the Accounts view can create a customer and linked account atomically; the Transactions view can add a transaction with metadata; both use server-side validation and are persisted to SQLite.
- **Rule thresholds:** high value ≥ ₹100,000 (+65); otherwise large ticket ≥ ₹50,000 (+42); cross-border ≥ ₹10,000 (+35); velocity ≥ 4 clustered transactions (+25); ATM ≥ ₹25,000 (+20). Alerts begin at score 55.
- **No third-party packages:** Python standard library only.

## Questions and strong answers

### 1. What is a DBMS?
A Database Management System is software used to define, store, retrieve, update, and administer data while enforcing rules for correctness, consistency, and controlled access. PHANTOM uses SQLite as the DBMS.

### 2. Why did you choose SQLite?
SQLite is a real relational database that stores data in a portable local file. It supports SQL, joins, constraints, views, triggers, indexes, and ACID transactions, while requiring no separate server installation. It fits a self-contained educational demo. For a production, multi-user platform, I would evaluate PostgreSQL or another server DBMS.

### 3. Why not store everything in one table?
Customer information, account information, transactions, alert decisions, and audit events have different lifecycles and relationships. Separating them reduces repeated data and update anomalies. Foreign keys then ensure related records refer to valid entities.

### 4. What is the primary key in each core table?
`customers.id`, `accounts.id`, `transactions.id`, `fraud_alerts.id`, and `audit_logs.id` are the primary keys. The transaction external reference and customer email are also unique, and `fraud_alerts.transaction_id` is unique so this demo permits at most one alert row per transaction.

### 5. Explain the main foreign keys.
`accounts.customer_id` references a customer; `transactions.account_id` references its account; `transactions.counterparty_account_id` optionally references another account; and an alert references both the transaction and account involved. This enforces referential integrity.

### 6. What is normalization? How is it used here?
Normalization organizes data to reduce unnecessary duplication and prevent insertion, update, and deletion anomalies. PHANTOM separates customer, account, transaction, alert, and audit records. Non-key fields describe their own entity rather than being repeated in unrelated tables. The core design targets 3NF for these entities.

### 7. What is the difference between a primary key and a foreign key?
A primary key uniquely identifies a row in its table. A foreign key references a key in another table (or the same table) and enforces relationship validity. For example, `accounts.id` is a primary key while `accounts.customer_id` is a foreign key.

### 8. What does ACID stand for?
Atomicity, Consistency, Isolation, and Durability. PHANTOM's simulated transfer is atomic: both balance updates and the transaction/audit inserts commit together, or the changes roll back on error. SQLite handles the database-level guarantees within the transaction boundary.

### 9. How does the transfer avoid an overdraft?
The API checks the account and calls a conditional update requiring `balance >= amount`. The `accounts.balance` CHECK constraint and a `BEFORE UPDATE` trigger provide additional protection against a negative balance. If debit validation fails, the server rolls the entire database transaction back.

### 10. What is the purpose of `BEGIN IMMEDIATE`?
It starts a write transaction early and obtains SQLite's reserved write lock before checking/updating balances. That reduces the chance that two concurrent transfers both pass a stale balance check. It does not replace validation; all steps still occur in one transaction.

### 11. What is a trigger? Name the triggers in your project.
A trigger runs automatically in response to a database event. PHANTOM's transaction insert trigger writes a transaction-creation audit event; the alert insert trigger writes alert-creation evidence; and the balance trigger aborts an update that would make a balance negative.

### 12. Why do you use views?
Views store reusable SQL query definitions. `v_account_summary` combines account/customer data with pre-aggregated transaction and alert metrics. `v_open_alerts` combines active alerts with their transaction and customer context. They simplify application queries and demonstrate logical data abstraction.

### 13. Why are indexes required?
Indexes can speed up filtering, joins, and sorting by frequently searched fields. PHANTOM defines indexes for transaction account/date, transaction date/risk/status, alert status/severity/account, account/customer relationship, and audit creation time. Indexes cost storage and add work on writes, so they should target useful query patterns.

### 14. What is a JOIN? Give an example from PHANTOM.
A JOIN combines rows from related tables using a related-column condition. For example, the dashboard's alert query joins `fraud_alerts`, `transactions`, `accounts`, and `customers` so an alert can display a customer name and merchant alongside its status and score.

### 15. How does the fraud detection algorithm work?
It scans recent transaction records and adds points for configured rules: large amounts, high-value cross-border transactions, high transaction velocity, and high-value ATM withdrawals. The score is capped at 100. At 55 or above it creates an alert unless one already exists for that transaction. These thresholds are illustrative, not a validated production model.

### 16. What are false positives and false negatives?
A false positive is a legitimate transaction incorrectly flagged. A false negative is suspicious or fraudulent activity the system misses. PHANTOM includes a False Positive status to demonstrate the analyst feedback workflow. Evaluating real precision/recall would require labeled, representative data, which this demo does not contain.

### 17. Why does the project use parameterized SQL?
Search values are passed as parameters rather than concatenated into SQL text. This reduces SQL injection risk and handles quoting safely. Table/column names are fixed by the application rather than taken from user input.

### 18. What does the audit trail do?
It records key events such as transaction creation, alert creation, scan completion, transfer completion, and analyst alert decisions. It stores actor, action, entity reference, details, and timestamp, providing traceability for the demo. A production audit design would require stronger access controls and tamper resistance.

### 19. How do you test the project?
The included `tests/smoke_test.py` starts the server with a temporary database and checks static UI delivery, seeded metrics, scan execution, alert updates, successful transfers, insufficient-funds rejection, customer/account creation, manual transaction creation, duplicate email rejection, a fraud alert for a newly-entered high-risk transaction, audit events, CSV export, and reports. It leaves the bundled database untouched. The included test suite passed in the build environment.

### 20. What are the limitations?
There is no login/role-based access, no real banking integration, and no real transaction data. The rules are interpretable thresholds and are not calibrated or certified. SQLite is used for a portable single-user demo; a production system would need security hardening, monitoring, formal testing, access control, privacy controls, and a multi-user architecture.

### 21. How would you improve the project?
Add authentication and least-privilege roles, configurable rules, case notes, metrics for false-positive rates, more comprehensive tests, schema migrations, and backups. For production-scale simultaneous workloads I would evaluate PostgreSQL with a hardened API and deployment controls.

### 22. What does `EXPLAIN QUERY PLAN` show?
It shows SQLite's planned approach to executing a query, including whether it uses an index or scans a table. I use it as a demonstration to discuss query optimization and the practical role of indexes; actual runtime improvements should be measured on a larger representative dataset.

## Recommended live demo (3–4 minutes)

1. Launch `run_phantom.bat`; open `http://127.0.0.1:8080`.
2. **Show the database is populated:** Overview shows real aggregate results; the seed has 18 fictional customers, 24 accounts, 94 transactions, and 15 seeded alerts.
3. **Add a customer:** Open Accounts → **Add customer / account**. Use a fictional name and unique `.test` email, a Medium risk tier, Savings, and an opening balance such as ₹200,000. Save and point out the newly generated account ID.
4. **Add a transaction:** Open Transactions → **Add transaction**. Pick that account; merchant `Nova Electronics`, category `E-commerce`, amount ₹125,000, type Payment, status Completed, channel Online, location `Singapore, SG`, and mark International. Save.
5. **Run fraud detection:** Open Fraud alerts → **Run threat scan**. High-value (+65) and cross-border (+35) rules combine to a score of 100, so the newly entered transaction should create a Critical alert. This demonstrates a real data entry → SQL insert → rule scan → alert insert workflow.
6. **Show traceability:** Move that alert to Investigating, then open Audit trail to show the customer, account, transaction, scan, alert, and analyst action events.
7. If time remains, simulate a ₹500–₹1,000 transfer between two active accounts, then explain the transfer is atomic and reject an amount larger than the source balance to show rollback.

Keep names/emails fictional, and be clear that the transaction/transfer data is local simulation only. If the live demo time is very short, do steps 3–6: that is the strongest proof it is an interactive working application rather than a static dashboard.

## Likely viva trap to avoid

Do not claim that PHANTOM detects actual fraud with production accuracy, uses AI/ML, connects to real banks, or guarantees every risky transaction is caught. Explain that it demonstrates relational database design and a transparent heuristic rule engine using fictional data.
