#!/usr/bin/env python3
"""End-to-end smoke tests. Runs against a temporary DB so bundled demo data is unchanged."""
from __future__ import annotations
import json, os, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def req(base, path, method='GET', data=None):
    payload = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(base + path, data=payload, method=method,
                                     headers={'Content-Type':'application/json'} if payload else {})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()

def assert_true(condition, message):
    if not condition: raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix='phantom-smoke-') as temp:
        port = free_port(); base = f'http://127.0.0.1:{port}'
        env = os.environ.copy(); env['PHANTOM_PORT'] = str(port); env['PHANTOM_HOST'] = '127.0.0.1'; env['PHANTOM_DB_PATH'] = str(Path(temp)/'smoke.db')
        process = subprocess.Popen([sys.executable, str(ROOT/'app.py')], cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    status, _, body = req(base, '/api/health')
                    if status == 200: break
                except Exception: pass
                if process.poll() is not None: raise RuntimeError('PHANTOM server exited during startup')
                time.sleep(.2)
            else: raise RuntimeError('PHANTOM server did not start in time')

            status, _, body = req(base, '/')
            assert_true(status == 200 and b'PHANTOM' in body, 'Static UI route failed')
            status, _, body = req(base, '/api/dashboard')
            dash = json.loads(body)
            assert_true(status == 200 and dash['metrics']['total_transactions'] >= 80, 'Seeded dashboard metrics failed')
            assert_true(dash['metrics']['monitored_accounts'] >= 15, 'Account seed count looks wrong')

            status, _, body = req(base, '/api/scan', 'POST', {})
            scan = json.loads(body)
            assert_true(status == 200 and scan['scanned'] >= 80, 'Threat scan endpoint failed')
            assert_true(scan['created_alerts'] >= 1, 'Threat scan should create the seeded unreviewed high-value alert')

            status, _, body = req(base, '/api/alerts?status=all')
            alerts = json.loads(body)['items']
            assert_true(status == 200 and len(alerts) >= 10, 'Alert API failed')
            alert_id = alerts[0]['id']
            status, _, body = req(base, f'/api/alerts/{alert_id}/decision', 'POST', {'status':'INVESTIGATING','actor':'Smoke Test','note':'Automated test'})
            assert_true(status == 200 and json.loads(body)['status'] == 'INVESTIGATING', 'Alert decision workflow failed')

            status, _, body = req(base, '/api/accounts')
            accounts = json.loads(body)['items']
            active = [a for a in accounts if a['account_status'] == 'ACTIVE' and a['balance'] > 200]
            assert_true(len(active) >= 2, 'Seeded active accounts missing')
            source, destination = active[0], next(a for a in active[1:] if a['account_id'] != active[0]['account_id'])
            amount = 100.0
            status, _, body = req(base, '/api/transfer', 'POST', {'from_account':source['account_id'],'to_account':destination['account_id'],'amount':amount,'note':'Smoke test transfer'})
            transfer = json.loads(body)
            assert_true(status == 201 and transfer['amount'] == amount, 'Atomic transfer failed')

            status, _, body = req(base, '/api/accounts')
            check = {a['account_id']:a for a in json.loads(body)['items']}
            assert_true(abs(check[source['account_id']]['balance'] - (source['balance']-amount)) < .02, 'Source balance not debited correctly')
            assert_true(abs(check[destination['account_id']]['balance'] - (destination['balance']+amount)) < .02, 'Destination balance not credited correctly')

            status, _, body = req(base, '/api/transfer', 'POST', {'from_account':source['account_id'],'to_account':destination['account_id'],'amount':9999999,'note':'Must fail'})
            assert_true(status == 400 and b'Insufficient funds' in body, 'Insufficient-funds transfer must be rejected')
            status, _, body = req(base, '/api/customers', 'POST', {
                'full_name':'Demo Aanya Kapoor', 'email':'aanya.kapoor@example.test', 'phone':'+91-90000-19999',
                'risk_tier':'MEDIUM', 'account_type':'SAVINGS', 'opening_balance':75000, 'country':'IN'
            })
            new_customer = json.loads(body)
            assert_true(status == 201 and new_customer['account_id'].startswith('AC-'), 'Customer/account creation failed')
            status, _, body = req(base, '/api/customers?q=Aanya')
            assert_true(status == 200 and any(x['email']=='aanya.kapoor@example.test' for x in json.loads(body)['items']), 'New customer did not persist')

            status, _, body = req(base, '/api/transactions', 'POST', {
                'account_id':new_customer['account_id'], 'merchant':'Nova Electronics', 'category':'E-commerce',
                'amount':125000, 'transaction_type':'PAYMENT', 'status':'COMPLETED', 'channel':'ONLINE',
                'location':'Singapore, SG', 'ip_address':'192.0.2.77', 'device_id':'DEMO-DEVICE-77', 'is_international':True
            })
            new_tx = json.loads(body)
            assert_true(status == 201 and new_tx['risk_score'] == 5, 'Manual transaction creation failed')
            status, _, body = req(base, '/api/transactions?q=Nova%20Electronics')
            assert_true(status == 200 and any(x['external_ref']==new_tx['reference'] for x in json.loads(body)['items']), 'New transaction did not persist')
            status, _, body = req(base, '/api/scan', 'POST', {})
            scan_new = json.loads(body)
            assert_true(status == 200 and scan_new['created_alerts'] >= 1, 'Threat scan did not flag newly-entered risky transaction')
            status, _, body = req(base, '/api/alerts?status=all&q=Nova')
            assert_true(status == 200 and any(x['external_ref']==new_tx['reference'] for x in json.loads(body)['items']), 'New alert was not linked to the manually-entered transaction')

            status, _, body = req(base, '/api/customers', 'POST', {
                'full_name':'Duplicate Email', 'email':'aanya.kapoor@example.test', 'risk_tier':'LOW',
                'account_type':'SAVINGS', 'opening_balance':1, 'country':'IN'
            })
            assert_true(status == 409, 'Duplicate email should be rejected with HTTP 409')
            status, headers, body = req(base, '/api/export/transactions')
            assert_true(status == 200 and 'text/csv' in headers.get('Content-Type','') and b'external_ref' in body, 'CSV export failed')
            status, _, body = req(base, '/api/reports')
            assert_true(status == 200 and b'category_spend' in body, 'Report endpoint failed')
            status, _, body = req(base, '/api/audit?limit=30')
            assert_true(status == 200 and b'MANUAL_TRANSACTION_ADDED' in body and b'CUSTOMER_CREATED' in body, 'Audit trail missing user-entered data events')
            print('PHANTOM smoke tests passed: dashboard, scan, alert review, atomic transfer/rollback, customer+account creation, manual transactions, duplicate validation, fraud alert for new data, audit trail, CSV export, reports.')
        finally:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)

if __name__ == '__main__':
    main()