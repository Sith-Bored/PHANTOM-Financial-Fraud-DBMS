#!/usr/bin/env python3
"""PHANTOM - a local, educational Financial Fraud Intelligence DBMS.
Uses only Python's standard library and SQLite; no external services required."""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import re
import math
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PHANTOM_DB_PATH", str(ROOT / "data" / "phantom.db"))).expanduser().resolve()
SCHEMA_PATH = ROOT / "database" / "schema.sql"
SEED_PATH = ROOT / "database" / "seed.sql"
WEB_ROOT = ROOT / "web"
HOST = os.environ.get("PHANTOM_HOST", "127.0.0.1")
PORT = int(os.environ.get("PHANTOM_PORT", "8080"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize_database() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if count == 0 and SEED_PATH.exists():
            conn.executescript(SEED_PATH.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO audit_logs(actor, action, entity_type, entity_id, details) "
            "VALUES (?, ?, ?, ?, ?)",
            ("system", "APPLICATION_STARTED", "system", "PHANTOM", "Local demo application initialized"),
        )
    finally:
        conn.close()


def row_dict(row):
    return dict(row) if row is not None else None


def rows_dict(rows):
    return [dict(r) for r in rows]


def money(value: float) -> float:
    return round(float(value or 0), 2)


def dashboard_data(conn: sqlite3.Connection) -> dict:
    metrics = conn.execute("""
        SELECT
          (SELECT COUNT(*) FROM transactions) AS total_transactions,
          (SELECT COALESCE(SUM(amount),0) FROM transactions WHERE status='COMPLETED') AS total_volume,
          (SELECT COUNT(*) FROM fraud_alerts WHERE status IN ('OPEN','INVESTIGATING')) AS active_alerts,
          (SELECT COUNT(*) FROM fraud_alerts WHERE status IN ('OPEN','INVESTIGATING') AND severity IN ('HIGH','CRITICAL')) AS high_alerts,
          (SELECT COUNT(*) FROM accounts WHERE status='ACTIVE') AS monitored_accounts,
          (SELECT COALESCE(SUM(t.amount),0) FROM transactions t JOIN fraud_alerts f ON f.transaction_id=t.id WHERE f.status IN ('OPEN','INVESTIGATING')) AS flagged_exposure,
          (SELECT COUNT(*) FROM fraud_alerts WHERE status='RESOLVED') AS resolved_alerts,
          (SELECT COUNT(*) FROM fraud_alerts WHERE status='FALSE_POSITIVE') AS false_positives
    """).fetchone()
    now = datetime.now(timezone.utc)
    month_keys = []
    for offset in range(5, -1, -1):
        year = now.year
        month = now.month - offset
        while month <= 0:
            month += 12
            year -= 1
        month_keys.append(f"{year:04d}-{month:02d}")
    trend_rows = conn.execute("""
        SELECT substr(created_at,1,7) AS month, COUNT(*) AS count,
               COALESCE(SUM(amount),0) AS volume
        FROM transactions GROUP BY substr(created_at,1,7)
    """).fetchall()
    trend_map = {r["month"]: r for r in trend_rows}
    trend = []
    for key in month_keys:
        r = trend_map.get(key)
        dt = datetime.strptime(key, "%Y-%m")
        trend.append({"month": dt.strftime("%b"), "key": key, "count": int(r["count"]) if r else 0,
                      "volume": money(r["volume"]) if r else 0})
    categories = rows_dict(conn.execute("""
        SELECT category, COUNT(*) AS count, COALESCE(SUM(amount),0) AS volume
        FROM transactions GROUP BY category ORDER BY volume DESC LIMIT 6
    """).fetchall())
    risk_distribution = rows_dict(conn.execute("""
        SELECT CASE WHEN risk_score >= 70 THEN 'High risk'
                    WHEN risk_score >= 40 THEN 'Medium risk' ELSE 'Low risk' END AS label,
               COUNT(*) AS count
        FROM transactions GROUP BY label ORDER BY CASE label WHEN 'High risk' THEN 1 WHEN 'Medium risk' THEN 2 ELSE 3 END
    """).fetchall())
    latest_alerts = rows_dict(conn.execute("""
        SELECT * FROM v_open_alerts ORDER BY created_at DESC LIMIT 6
    """).fetchall())
    latest_transactions = rows_dict(conn.execute("""
        SELECT t.id, t.external_ref, t.merchant, t.category, t.amount, t.currency,
               t.status, t.risk_score, t.location, t.channel, t.created_at,
               t.account_id, c.full_name AS customer_name
        FROM transactions t JOIN accounts a ON a.id=t.account_id
        JOIN customers c ON c.id=a.customer_id
        ORDER BY t.created_at DESC, t.id DESC LIMIT 8
    """).fetchall())
    activity = rows_dict(conn.execute("""
        SELECT id, actor, action, entity_type, entity_id, details, created_at
        FROM audit_logs ORDER BY id DESC LIMIT 6
    """).fetchall())
    return {
        "metrics": {k: (money(v) if k in ("total_volume", "flagged_exposure") else int(v)) for k, v in dict(metrics).items()},
        "trend": trend, "categories": categories, "risk_distribution": risk_distribution,
        "latest_alerts": latest_alerts, "latest_transactions": latest_transactions, "activity": activity,
        "generated_at": utc_now(),
    }


def transaction_query(conn: sqlite3.Connection, params: dict) -> list[dict]:
    sql = """
        SELECT t.*, c.full_name AS customer_name
        FROM transactions t JOIN accounts a ON a.id=t.account_id
        JOIN customers c ON c.id=a.customer_id WHERE 1=1
    """
    args = []
    q = (params.get("q") or [""])[0].strip()
    if q:
        sql += " AND (t.external_ref LIKE ? OR t.merchant LIKE ? OR c.full_name LIKE ? OR t.account_id LIKE ? OR t.category LIKE ?)"
        args.extend([f"%{q}%"] * 5)
    risk = (params.get("risk") or [""])[0]
    if risk == "high":
        sql += " AND t.risk_score >= 70"
    elif risk == "medium":
        sql += " AND t.risk_score >= 40 AND t.risk_score < 70"
    elif risk == "low":
        sql += " AND t.risk_score < 40"
    status = (params.get("status") or [""])[0]
    if status in ("COMPLETED", "PENDING", "DECLINED", "REVIEW"):
        sql += " AND t.status=?"
        args.append(status)
    sql += " ORDER BY t.created_at DESC, t.id DESC LIMIT 250"
    return rows_dict(conn.execute(sql, args).fetchall())


def alert_query(conn: sqlite3.Connection, params: dict) -> list[dict]:
    sql = """
        SELECT fa.*, t.external_ref, t.merchant, t.category, t.amount, t.currency,
               t.location, t.channel, t.created_at AS transaction_created_at,
               a.balance AS account_balance, c.full_name AS customer_name, c.email AS customer_email
        FROM fraud_alerts fa JOIN transactions t ON t.id=fa.transaction_id
        JOIN accounts a ON a.id=fa.account_id JOIN customers c ON c.id=a.customer_id WHERE 1=1
    """
    args = []
    status = (params.get("status") or ["all"])[0]
    if status in ("OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"):
        sql += " AND fa.status=?"
        args.append(status)
    severity = (params.get("severity") or [""])[0]
    if severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        sql += " AND fa.severity=?"
        args.append(severity)
    q = (params.get("q") or [""])[0].strip()
    if q:
        sql += " AND (t.external_ref LIKE ? OR t.merchant LIKE ? OR c.full_name LIKE ? OR fa.rule_name LIKE ? OR fa.reason LIKE ?)"
        args.extend([f"%{q}%"] * 5)
    sql += " ORDER BY CASE fa.status WHEN 'OPEN' THEN 0 WHEN 'INVESTIGATING' THEN 1 ELSE 2 END, fa.score DESC, fa.created_at DESC LIMIT 250"
    return rows_dict(conn.execute(sql, args).fetchall())


def run_scan(conn: sqlite3.Connection) -> dict:
    conn.execute("BEGIN IMMEDIATE")
    created = 0
    updated = 0
    scanned = 0
    try:
        txs = conn.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 1000").fetchall()
        existing_ids = {r[0] for r in conn.execute("SELECT transaction_id FROM fraud_alerts")}
        for tx in txs:
            scanned += 1
            score = 0
            reasons = []
            rules = []
            amt = float(tx["amount"])
            if amt >= 100000:
                score += 65; rules.append("HIGH_VALUE"); reasons.append("Transaction amount exceeds INR 100,000 threshold")
            elif amt >= 50000:
                score += 42; rules.append("LARGE_TICKET"); reasons.append("Large transaction exceeds INR 50,000 threshold")
            if tx["is_international"] and amt >= 10000:
                score += 35; rules.append("CROSS_BORDER"); reasons.append("High-value international transaction")
            rapid = conn.execute("""
                SELECT COUNT(*) FROM transactions
                WHERE account_id=? AND ABS((julianday(created_at)-julianday(?))*1440.0) <= 10
            """, (tx["account_id"], tx["created_at"])).fetchone()[0]
            if rapid >= 4:
                score += 25; rules.append("VELOCITY"); reasons.append(f"Velocity rule: {rapid} transactions clustered within a 20-minute window")
            if tx["channel"] == "ATM" and amt >= 25000:
                score += 20; rules.append("ATM_PATTERN"); reasons.append("High-value ATM withdrawal requires review")
            score = min(100, max(score, int(tx["risk_score"])))
            if score != int(tx["risk_score"]):
                conn.execute("UPDATE transactions SET risk_score=? WHERE id=?", (score, tx["id"]))
                updated += 1
            if score >= 55 and tx["id"] not in existing_ids:
                severity = "CRITICAL" if score >= 90 else "HIGH" if score >= 70 else "MEDIUM"
                conn.execute("""
                    INSERT INTO fraud_alerts(transaction_id, account_id, severity, score, rule_name, reason, status, assigned_to)
                    VALUES (?, ?, ?, ?, ?, ?, 'OPEN', 'Fraud Operations')
                """, (tx["id"], tx["account_id"], severity, score,
                      " + ".join(rules) if rules else "RISK_SCORE", "; ".join(reasons) if reasons else "Transaction risk score exceeded configured threshold"))
                existing_ids.add(tx["id"])
                created += 1
        conn.execute("INSERT INTO audit_logs(actor, action, entity_type, entity_id, details) VALUES (?,?,?,?,?)",
                     ("fraud-engine", "SCAN_COMPLETED", "scan", "manual", f"Scanned {scanned} transactions; created {created} alerts; updated {updated} risk scores"))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"scanned": scanned, "created_alerts": created, "updated_scores": updated}


class PhantomHandler(BaseHTTPRequestHandler):
    server_version = "PHANTOM/1.0"

    def log_message(self, fmt, *args):
        # concise server console log
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 1_000_000:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON") from exc

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)
        if path.startswith("/api/"):
            conn = connect()
            try:
                if path == "/api/health":
                    db_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
                    self.send_json({"ok": True, "app": "PHANTOM", "database": "SQLite", "tables": db_count, "time": utc_now()})
                elif path == "/api/dashboard":
                    self.send_json(dashboard_data(conn))
                elif path == "/api/transactions":
                    self.send_json({"items": transaction_query(conn, params)})
                elif path == "/api/alerts":
                    self.send_json({"items": alert_query(conn, params)})
                elif path == "/api/accounts":
                    q = (params.get("q") or [""])[0].strip()
                    rows = conn.execute("""
                        SELECT v.*, c.phone, c.risk_tier, c.id AS customer_id
                        FROM v_account_summary v JOIN customers c ON c.email=v.customer_email
                        WHERE (?='' OR v.account_id LIKE ? OR v.customer_name LIKE ? OR v.customer_email LIKE ?)
                        ORDER BY v.active_alert_count DESC, v.balance DESC
                    """, (q, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
                    self.send_json({"items": rows_dict(rows)})
                elif path == "/api/customers":
                    q = (params.get("q") or [""])[0].strip()
                    rows = conn.execute("""
                        SELECT c.id, c.full_name, c.email, c.phone, c.risk_tier, c.created_at,
                               COUNT(a.id) AS account_count,
                               COALESCE(SUM(a.balance),0) AS total_balance
                        FROM customers c LEFT JOIN accounts a ON a.customer_id=c.id
                        WHERE (?='' OR c.full_name LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)
                        GROUP BY c.id ORDER BY c.created_at DESC, c.id DESC LIMIT 250
                    """, (q, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
                    self.send_json({"items": rows_dict(rows)})
                elif path == "/api/audit":
                    limit = min(max(int((params.get("limit") or ["80"])[0]), 1), 250)
                    self.send_json({"items": rows_dict(conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall())})
                elif path == "/api/reports":
                    self.send_json(self.report_data(conn))
                elif path == "/api/export/transactions":
                    items = transaction_query(conn, params)
                    output = io.StringIO()
                    if items:
                        writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
                        writer.writeheader(); writer.writerows(items)
                    else:
                        output.write("id,external_ref,merchant,amount,currency,status,risk_score\n")
                    blob = output.getvalue().encode("utf-8-sig")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="phantom_transactions.csv"')
                    self.send_header("Content-Length", str(len(blob)))
                    self.end_headers(); self.wfile.write(blob)
                else:
                    self.send_json({"error": "API endpoint not found"}, 404)
            except Exception as exc:
                traceback.print_exc()
                self.send_json({"error": str(exc)}, 500)
            finally:
                conn.close()
            return
        self.serve_static(path)

    def report_data(self, conn):
        return {
            "category_spend": rows_dict(conn.execute("SELECT category, COUNT(*) AS transaction_count, ROUND(SUM(amount),2) AS volume, ROUND(AVG(amount),2) AS average_ticket FROM transactions GROUP BY category ORDER BY volume DESC").fetchall()),
            "account_risk": rows_dict(conn.execute("SELECT account_id, customer_name, balance, active_alert_count, transaction_count FROM v_account_summary ORDER BY active_alert_count DESC, transaction_count DESC LIMIT 10").fetchall()),
            "alert_disposition": rows_dict(conn.execute("SELECT status, COUNT(*) AS count FROM fraud_alerts GROUP BY status ORDER BY count DESC").fetchall()),
            "channel_volume": rows_dict(conn.execute("SELECT channel, COUNT(*) AS count, ROUND(SUM(amount),2) AS volume FROM transactions GROUP BY channel ORDER BY volume DESC").fetchall()),
            "query_examples": [
                {"title": "Accounts with unresolved alerts", "description": "Uses a view joining customers, accounts, transactions and alerts.", "sql": "SELECT account_id, customer_name, active_alert_count FROM v_account_summary WHERE active_alert_count > 0 ORDER BY active_alert_count DESC;"},
                {"title": "High-risk transaction volume", "description": "Groups risk-scored activity into an operational metric.", "sql": "SELECT COUNT(*) AS tx_count, SUM(amount) AS exposure FROM transactions WHERE risk_score >= 70;"},
                {"title": "Alert disposition", "description": "Measures investigation outcomes using aggregation.", "sql": "SELECT status, COUNT(*) FROM fraud_alerts GROUP BY status;"},
            ],
        }

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        try:
            body = self.read_json()
            conn = connect()
            try:
                if path == "/api/scan":
                    result = run_scan(conn)
                    self.send_json({"ok": True, **result})
                elif path == "/api/transfer":
                    result = self.transfer(conn, body)
                    self.send_json({"ok": True, **result}, 201)
                elif path == "/api/customers":
                    result = self.create_customer_account(conn, body)
                    self.send_json({"ok": True, **result}, 201)
                elif path == "/api/transactions":
                    result = self.create_transaction(conn, body)
                    self.send_json({"ok": True, **result}, 201)
                else:
                    match = re.fullmatch(r"/api/alerts/(\d+)/decision", path)
                    if match:
                        result = self.decide_alert(conn, int(match.group(1)), body)
                        self.send_json({"ok": True, **result})
                    else:
                        self.send_json({"error": "API endpoint not found"}, 404)
            finally:
                conn.close()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
        except LookupError as exc:
            self.send_json({"error": str(exc)}, 404)
        except sqlite3.IntegrityError as exc:
            self.send_json({"error": str(exc)}, 409)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"error": str(exc)}, 500)

    def create_customer_account(self, conn, body):
        """Create a customer and opening account together as one DB transaction."""
        name = str(body.get("full_name", "")).strip()
        email = str(body.get("email", "")).strip().lower()
        phone = str(body.get("phone", "")).strip()[:40]
        tier = str(body.get("risk_tier", "LOW")).upper()
        account_type = str(body.get("account_type", "SAVINGS")).upper()
        country = str(body.get("country", "IN")).strip().upper()[:2] or "IN"
        try:
            opening_balance = round(float(body.get("opening_balance", 0)), 2)
        except (ValueError, TypeError):
            raise ValueError("Opening balance must be a valid number")
        if not name or len(name) > 120:
            raise ValueError("Customer name is required and must be 120 characters or fewer")
        if not email or len(email) > 190 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address (use fictional .test emails for demo data)")
        if tier not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError("Risk tier must be LOW, MEDIUM, or HIGH")
        if account_type not in {"CURRENT", "SAVINGS", "WALLET"}:
            raise ValueError("Account type must be CURRENT, SAVINGS, or WALLET")
        if not math.isfinite(opening_balance) or not (0 <= opening_balance <= 50_000_000):
            raise ValueError("Opening balance must be between INR 0 and INR 5 crore")
        if not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("Country must be a two-letter country code, for example IN")
        conn.execute("BEGIN IMMEDIATE")
        try:
            customer_cur = conn.execute(
                "INSERT INTO customers(full_name,email,phone,risk_tier) VALUES (?,?,?,?)",
                (name, email, phone, tier),
            )
            customer_id = customer_cur.lastrowid
            # Random, readable demo account identifier with a collision check.
            account_id = None
            for _ in range(8):
                candidate = "AC-" + os.urandom(3).hex().upper()
                if conn.execute("SELECT 1 FROM accounts WHERE id=?", (candidate,)).fetchone() is None:
                    account_id = candidate
                    break
            if account_id is None:
                raise RuntimeError("Could not allocate a unique account ID; please retry")
            conn.execute(
                "INSERT INTO accounts(id,customer_id,account_type,balance,currency,status,country) VALUES (?,?,?,?,?,'ACTIVE',?)",
                (account_id, customer_id, account_type, opening_balance, "INR", country),
            )
            conn.execute(
                "INSERT INTO audit_logs(actor,action,entity_type,entity_id,details) VALUES (?,?,?,?,?)",
                ("demo-operator", "CUSTOMER_CREATED", "customer", str(customer_id), f"Created customer {name}; email={email}"),
            )
            conn.execute(
                "INSERT INTO audit_logs(actor,action,entity_type,entity_id,details) VALUES (?,?,?,?,?)",
                ("demo-operator", "ACCOUNT_CREATED", "account", account_id, f"Opened {account_type} account for customer_id={customer_id}; opening_balance=INR {opening_balance:.2f}"),
            )
            conn.commit()
            return {"customer_id": customer_id, "account_id": account_id, "full_name": name,
                    "email": email, "opening_balance": opening_balance,
                    "message": "Customer and account created successfully"}
        except Exception:
            conn.rollback()
            raise

    def create_transaction(self, conn, body):
        """Add an analyst-entered transaction record for subsequent fraud scanning."""
        account_id = str(body.get("account_id", "")).strip()
        merchant = str(body.get("merchant", "")).strip()
        category = str(body.get("category", "Other")).strip() or "Other"
        tx_type = str(body.get("transaction_type", "PAYMENT")).upper()
        status = str(body.get("status", "COMPLETED")).upper()
        channel = str(body.get("channel", "ONLINE")).upper()
        location = str(body.get("location", "Coimbatore, IN")).strip() or "Coimbatore, IN"
        ip_address = str(body.get("ip_address", "192.0.2.10")).strip() or "192.0.2.10"
        device_id = str(body.get("device_id", "PHANTOM-MANUAL")).strip() or "PHANTOM-MANUAL"
        international = body.get("is_international", False)
        try:
            amount = round(float(body.get("amount", 0)), 2)
        except (ValueError, TypeError):
            raise ValueError("Transaction amount must be a valid number")
        if not account_id:
            raise ValueError("Select an account for this transaction")
        if not merchant or len(merchant) > 120:
            raise ValueError("Merchant or transaction description is required (max 120 characters)")
        if len(category) > 60:
            raise ValueError("Category must be 60 characters or fewer")
        if not math.isfinite(amount) or not (0 < amount <= 10_000_000):
            raise ValueError("Amount must be greater than 0 and no more than INR 1 crore")
        if tx_type not in {"PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT", "REFUND"}:
            raise ValueError("Choose a valid transaction type")
        if status not in {"COMPLETED", "PENDING", "DECLINED", "REVIEW"}:
            raise ValueError("Choose a valid transaction status")
        if channel not in {"ONLINE", "POS", "ATM", "MOBILE", "BRANCH"}:
            raise ValueError("Choose a valid channel")
        if len(location) > 120 or len(ip_address) > 64 or len(device_id) > 64:
            raise ValueError("Location, IP address, or device ID exceeds its permitted length")
        international = 1 if str(international).lower() in {"1", "true", "yes", "on"} else 0
        account = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        if account is None:
            raise LookupError("Selected account was not found. Refresh the page and try again.")
        if account["status"] == "CLOSED":
            raise ValueError("Cannot record a new transaction against a closed account")
        reference = "USR-" + datetime.now().strftime("%y%m%d%H%M%S") + "-" + os.urandom(2).hex().upper()
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute("""
                INSERT INTO transactions(external_ref,account_id,merchant,category,amount,currency,
                    transaction_type,status,location,ip_address,device_id,channel,is_international,risk_score,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,5,?)
            """, (reference, account_id, merchant, category, amount, account["currency"], tx_type,
                  status, location, ip_address, device_id, channel, international, utc_now()))
            tx_id = cur.lastrowid
            conn.execute(
                "INSERT INTO audit_logs(actor,action,entity_type,entity_id,details,ip_address) VALUES (?,?,?,?,?,?)",
                ("demo-operator", "MANUAL_TRANSACTION_ADDED", "transaction", str(tx_id),
                 f"Added {reference}; account={account_id}; merchant={merchant}; amount={amount:.2f} {account['currency']}; status={status}", ip_address),
            )
            conn.commit()
            return {"transaction_id": tx_id, "reference": reference, "account_id": account_id,
                    "merchant": merchant, "amount": amount, "currency": account["currency"],
                    "risk_score": 5, "message": "Transaction added. Run a threat scan to evaluate it."}
        except Exception:
            conn.rollback()
            raise

    def transfer(self, conn, body):
        from_id = str(body.get("from_account", "")).strip()
        to_id = str(body.get("to_account", "")).strip()
        try:
            amount = round(float(body.get("amount", 0)), 2)
        except (ValueError, TypeError):
            raise ValueError("Amount must be a valid number")
        if not from_id or not to_id:
            raise ValueError("Select both source and destination accounts")
        if from_id == to_id:
            raise ValueError("Source and destination accounts must be different")
        if not (0 < amount <= 10_000_000):
            raise ValueError("Amount must be greater than 0 and no more than INR 1 crore")
        note = str(body.get("note", "Demo transfer")).strip()[:120] or "Demo transfer"
        conn.execute("BEGIN IMMEDIATE")
        try:
            source = conn.execute("SELECT * FROM accounts WHERE id=?", (from_id,)).fetchone()
            destination = conn.execute("SELECT * FROM accounts WHERE id=?", (to_id,)).fetchone()
            if source is None or destination is None:
                raise LookupError("One or both accounts were not found")
            if source["status"] != "ACTIVE" or destination["status"] != "ACTIVE":
                raise ValueError("Both accounts must be active to transfer funds")
            if source["currency"] != destination["currency"]:
                raise ValueError("Transfers require accounts with the same currency")
            cur = conn.execute("UPDATE accounts SET balance=ROUND(balance-?,2) WHERE id=? AND balance>=? AND status='ACTIVE'", (amount, from_id, amount))
            if cur.rowcount != 1:
                raise ValueError("Insufficient funds: transfer was cancelled safely")
            conn.execute("UPDATE accounts SET balance=ROUND(balance+?,2) WHERE id=?", (amount, to_id))
            ref = "TRF-" + datetime.now().strftime("%y%m%d%H%M%S") + "-" + os.urandom(2).hex().upper()
            cur = conn.execute("""
                INSERT INTO transactions(external_ref, account_id, counterparty_account_id, merchant, category, amount,
                    currency, transaction_type, status, location, ip_address, device_id, channel, is_international, risk_score, created_at)
                VALUES (?, ?, ?, ?, 'Transfer', ?, ?, 'TRANSFER', 'COMPLETED', 'Local demo', '127.0.0.1', 'PHANTOM-WEB', 'ONLINE', 0, 5, ?)
            """, (ref, from_id, to_id, f"Transfer to {to_id}", amount, source["currency"], utc_now()))
            tx_id = cur.lastrowid
            conn.execute("INSERT INTO audit_logs(actor, action, entity_type, entity_id, details, ip_address) VALUES (?,?,?,?,?,?)",
                         ("demo-operator", "TRANSFER_COMPLETED", "transaction", str(tx_id), f"{ref}: {from_id} -> {to_id}; amount={amount} {source['currency']}; note={note}", "127.0.0.1"))
            conn.commit()
            return {"transaction_id": tx_id, "reference": ref, "from_account": from_id, "to_account": to_id, "amount": amount, "currency": source["currency"], "message": "Demo transfer completed atomically"}
        except Exception:
            conn.rollback()
            raise

    def decide_alert(self, conn, alert_id, body):
        status = str(body.get("status", "")).upper()
        allowed = {"OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"}
        if status not in allowed:
            raise ValueError("Status must be OPEN, INVESTIGATING, RESOLVED, or FALSE_POSITIVE")
        actor = str(body.get("actor", "Fraud Operations")).strip()[:80] or "Fraud Operations"
        note = str(body.get("note", "")).strip()[:240]
        conn.execute("BEGIN IMMEDIATE")
        try:
            alert = conn.execute("SELECT * FROM fraud_alerts WHERE id=?", (alert_id,)).fetchone()
            if alert is None:
                raise LookupError("Alert not found")
            conn.execute("UPDATE fraud_alerts SET status=?, assigned_to=?, updated_at=? WHERE id=?", (status, actor, utc_now(), alert_id))
            conn.execute("INSERT INTO audit_logs(actor, action, entity_type, entity_id, details) VALUES (?,?,?,?,?)",
                         (actor, "ALERT_STATUS_CHANGED", "fraud_alert", str(alert_id), f"{alert['status']} -> {status}" + (f"; note={note}" if note else "")))
            conn.commit()
            return {"alert_id": alert_id, "status": status}
        except Exception:
            conn.rollback()
            raise

    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        target = (WEB_ROOT / path.lstrip("/")).resolve()
        try:
            target.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self.send_error(403, "Forbidden")
            return
        if not target.is_file():
            self.send_error(404, "Not found")
            return
        content = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json", "image/svg+xml"):
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


def main():
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), PhantomHandler)
    print("\n  PHANTOM | Financial Fraud Intelligence DBMS")
    print(f"  Running at: http://{HOST}:{PORT}")
    print(f"  Database:   {DB_PATH}")
    print("  Press Ctrl+C to stop. Use only fictional demo data.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPHANTOM stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()