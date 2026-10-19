PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY,
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    phone           TEXT,
    risk_tier       TEXT NOT NULL DEFAULT 'LOW' CHECK (risk_tier IN ('LOW','MEDIUM','HIGH')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS accounts (
    id              TEXT PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    account_type    TEXT NOT NULL CHECK (account_type IN ('CURRENT','SAVINGS','WALLET')),
    balance         REAL NOT NULL DEFAULT 0 CHECK (balance >= 0),
    currency        TEXT NOT NULL DEFAULT 'INR',
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','FROZEN','CLOSED')),
    country         TEXT NOT NULL DEFAULT 'IN',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    external_ref            TEXT NOT NULL UNIQUE,
    account_id              TEXT NOT NULL REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    counterparty_account_id TEXT REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    merchant                TEXT NOT NULL,
    category                TEXT NOT NULL,
    amount                  REAL NOT NULL CHECK (amount > 0),
    currency                TEXT NOT NULL DEFAULT 'INR',
    transaction_type        TEXT NOT NULL CHECK (transaction_type IN ('PAYMENT','TRANSFER','WITHDRAWAL','DEPOSIT','REFUND')),
    status                  TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('COMPLETED','PENDING','DECLINED','REVIEW')),
    location                TEXT NOT NULL DEFAULT 'Chennai, IN',
    ip_address              TEXT NOT NULL DEFAULT '192.0.2.1',
    device_id               TEXT NOT NULL DEFAULT 'DEV-UNKNOWN',
    channel                 TEXT NOT NULL DEFAULT 'ONLINE' CHECK (channel IN ('ONLINE','POS','ATM','MOBILE','BRANCH')),
    is_international        INTEGER NOT NULL DEFAULT 0 CHECK (is_international IN (0,1)),
    risk_score              INTEGER NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS fraud_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL UNIQUE REFERENCES transactions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    account_id      TEXT NOT NULL REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    severity        TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    score           INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    rule_name       TEXT NOT NULL,
    reason          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','INVESTIGATING','RESOLVED','FALSE_POSITIVE')),
    assigned_to     TEXT NOT NULL DEFAULT 'Unassigned',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    actor           TEXT NOT NULL DEFAULT 'system',
    action          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    details         TEXT NOT NULL DEFAULT '',
    ip_address      TEXT NOT NULL DEFAULT '127.0.0.1',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_account_created ON transactions(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_risk_score ON transactions(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON fraud_alerts(status, severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_account ON fraud_alerts(account_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);

DROP VIEW IF EXISTS v_account_summary;
CREATE VIEW v_account_summary AS
SELECT
    a.id AS account_id,
    c.full_name AS customer_name,
    c.email AS customer_email,
    a.account_type,
    a.balance,
    a.currency,
    a.status AS account_status,
    a.country,
    COALESCE(tx.transaction_count, 0) AS transaction_count,
    COALESCE(tx.completed_volume, 0) AS completed_volume,
    COALESCE(fa.active_alert_count, 0) AS active_alert_count
FROM accounts a
JOIN customers c ON c.id = a.customer_id
LEFT JOIN (
    SELECT account_id, COUNT(*) AS transaction_count,
           SUM(CASE WHEN status = 'COMPLETED' THEN amount ELSE 0 END) AS completed_volume
    FROM transactions GROUP BY account_id
) tx ON tx.account_id = a.id
LEFT JOIN (
    SELECT account_id, COUNT(*) AS active_alert_count
    FROM fraud_alerts WHERE status IN ('OPEN','INVESTIGATING') GROUP BY account_id
) fa ON fa.account_id = a.id;

CREATE VIEW IF NOT EXISTS v_open_alerts AS
SELECT fa.id AS alert_id, fa.severity, fa.score, fa.rule_name, fa.reason, fa.status,
       fa.created_at, t.external_ref, t.merchant, t.amount, t.currency,
       a.id AS account_id, c.full_name AS customer_name
FROM fraud_alerts fa
JOIN transactions t ON t.id = fa.transaction_id
JOIN accounts a ON a.id = fa.account_id
JOIN customers c ON c.id = a.customer_id
WHERE fa.status IN ('OPEN','INVESTIGATING');

CREATE TRIGGER IF NOT EXISTS trg_transaction_audit
AFTER INSERT ON transactions
BEGIN
    INSERT INTO audit_logs(actor, action, entity_type, entity_id, details, ip_address, created_at)
    VALUES ('transaction-engine', 'TRANSACTION_CREATED', 'transaction', NEW.id,
            'Reference=' || NEW.external_ref || '; account=' || NEW.account_id || '; amount=' || NEW.amount || ' ' || NEW.currency,
            NEW.ip_address, NEW.created_at);
END;

CREATE TRIGGER IF NOT EXISTS trg_alert_audit
AFTER INSERT ON fraud_alerts
BEGIN
    INSERT INTO audit_logs(actor, action, entity_type, entity_id, details, ip_address, created_at)
    VALUES ('fraud-engine', 'ALERT_CREATED', 'fraud_alert', NEW.id,
            'Severity=' || NEW.severity || '; score=' || NEW.score || '; rule=' || NEW.rule_name,
            '127.0.0.1', NEW.created_at);
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_negative_balance
BEFORE UPDATE OF balance ON accounts
WHEN NEW.balance < 0
BEGIN
    SELECT RAISE(ABORT, 'Insufficient funds: account balance cannot be negative');
END;
