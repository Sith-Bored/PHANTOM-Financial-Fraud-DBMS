"""Build the reproducible SQL demo seed file for PHANTOM (fictional data only)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random, calendar

ROOT=Path(__file__).resolve().parent
rng=random.Random(90210)
now=datetime.now(timezone.utc).replace(second=0,microsecond=0)
customers=[
 (1,'Aarav Mehta','aarav.mehta@example.test','+91-90000-10001','LOW'),
 (2,'Diya Sharma','diya.sharma@example.test','+91-90000-10002','MEDIUM'),
 (3,'Kabir Nair','kabir.nair@example.test','+91-90000-10003','LOW'),
 (4,'Ananya Rao','ananya.rao@example.test','+91-90000-10004','HIGH'),
 (5,'Ishaan Kapoor','ishaan.kapoor@example.test','+91-90000-10005','LOW'),
 (6,'Mira Iyer','mira.iyer@example.test','+91-90000-10006','MEDIUM'),
 (7,'Arjun Patel','arjun.patel@example.test','+91-90000-10007','HIGH'),
 (8,'Sara Khan','sara.khan@example.test','+91-90000-10008','LOW'),
 (9,'Reyansh Das','reyansh.das@example.test','+91-90000-10009','MEDIUM'),
 (10,'Aditi Menon','aditi.menon@example.test','+91-90000-10010','LOW'),
 (11,'Vihaan Joshi','vihaan.joshi@example.test','+91-90000-10011','MEDIUM'),
 (12,'Kiara Singh','kiara.singh@example.test','+91-90000-10012','LOW'),
 (13,'Dev Malhotra','dev.malhotra@example.test','+91-90000-10013','HIGH'),
 (14,'Myra Chawla','myra.chawla@example.test','+91-90000-10014','LOW'),
 (15,'Rohan Verma','rohan.verma@example.test','+91-90000-10015','MEDIUM'),
 (16,'Tara Krishnan','tara.krishnan@example.test','+91-90000-10016','LOW'),
 (17,'Neil Fernandez','neil.fernandez@example.test','+91-90000-10017','MEDIUM'),
 (18,'Zoya Ali','zoya.ali@example.test','+91-90000-10018','LOW'),
]
account_ids=[f'AC-{i:04d}' for i in range(1001,1019)]
account_types=['SAVINGS','CURRENT','WALLET']
accounts=[]
for i,c in enumerate(customers):
    aid=account_ids[i]
    typ=account_types[i%len(account_types)]
    balance=round(rng.choice([18000,32500,48600,72300,95000,125000,212000,388000])+rng.randint(0,999),2)
    status='FROZEN' if i in (6,12) else 'ACTIVE'
    accounts.append((aid,c[0],typ,balance,'INR',status,'IN'))
    # add a second wallet/current account for selected customers to support transfers
    if i in (0,2,4,7,9,13):
        j=len(accounts)+100
        accounts.append((f'WL-{i+1:03d}',c[0],'WALLET',round(rng.choice([2500,8000,12500,20000])+rng.randint(0,800),2),'INR','ACTIVE','IN'))

merchants_by_category={
 'E-commerce':['ShopKart','Nova Electronics','Urban Thread','Daily Market','GizmoHub','HomeNest'],
 'Travel':['Skyline Airways','MetroRail Online','TripSpring','Coastline Stays'],
 'Food & Dining':['Basil & Bean','QuickBite','Spice Avenue','Noodle Room'],
 'Utilities':['PowerGrid Billpay','FiberWave Telecom','City Water Utility'],
 'Entertainment':['StreamVerse','Pixel Arcade','CineNova Tickets'],
 'Transfer':['PeerPay Transfer','Wallet Move','Account Transfer'],
 'ATM':['ATM Cash Withdrawal'],
 'Healthcare':['WellSpring Pharmacy','CarePoint Clinic'],
 'Fuel':['RapidFuel','Metro Petrol'],
 'Education':['Campus Fees Portal','LearnLoop'],
}
cities=['Chennai, IN','Bengaluru, IN','Mumbai, IN','Hyderabad, IN','Pune, IN','New Delhi, IN','Kochi, IN','Coimbatore, IN']
channels=['ONLINE','POS','MOBILE','ATM','BRANCH']
amount_ranges={'E-commerce':(350,18500),'Travel':(1800,26000),'Food & Dining':(180,3200),'Utilities':(450,6800),'Entertainment':(250,2400),'Transfer':(500,24000),'ATM':(1000,12000),'Healthcare':(400,8500),'Fuel':(700,6500),'Education':(1200,38000)}
transactions=[]
external_idx=1
# Six months of demo traffic, giving the dashboard an actual trend line.
for month_offset in range(5,-1,-1):
    year=now.year; month=now.month-month_offset
    while month<=0: month+=12; year-=1
    last=calendar.monthrange(year,month)[1]
    for _ in range(13 if month_offset else 16):
        acct=rng.choice(accounts)
        cat=rng.choice(list(merchants_by_category.keys()))
        amount=round(rng.uniform(*amount_ranges[cat]),2)
        if cat=='ATM': channel='ATM'; tx_type='WITHDRAWAL'
        elif cat=='Transfer': channel=rng.choice(['ONLINE','MOBILE']); tx_type='TRANSFER'
        else: channel=rng.choice(channels); tx_type='PAYMENT'
        # Keep every regular demo event at or before the seed-generation timestamp.
        # Historical months use their full range; current-month events cap both day and clock.
        current_month = (year, month) == (now.year, now.month)
        latest_day = min(last, now.day) if current_month else last
        day=rng.randint(1,max(1,latest_day))
        if current_month and day == now.day:
            earliest_hour = 7 if now.hour >= 7 else 0
            hour=rng.randint(earliest_hour,now.hour)
            minute=rng.randint(0,now.minute if hour == now.hour else 59)
        else:
            hour=rng.randint(7,22); minute=rng.randint(0,59)
        dt=datetime(year,month,day,hour,minute,tzinfo=timezone.utc)
        intl=1 if rng.random()<0.055 else 0
        loc=rng.choice(['Singapore, SG','Dubai, AE','London, GB']) if intl else rng.choice(cities)
        risk= rng.choices([5,12,22,34,48,66,78],[.32,.23,.17,.12,.07,.04,.03])[0]
        status='COMPLETED'
        if rng.random()<.025: status='DECLINED'
        merchant=rng.choice(merchants_by_category[cat])
        ip=f'192.0.2.{rng.randint(1,240)}' if not intl else f'198.51.100.{rng.randint(1,240)}'
        device=f'DEV-{rng.randint(1,14):03d}'
        ref=f'PX-{year%100:02d}{month:02d}-{external_idx:05d}'
        transactions.append({'id':external_idx,'ref':ref,'account':acct[0],'counterparty':None,'merchant':merchant,'category':cat,'amount':amount,'currency':'INR','type':tx_type,'status':status,'location':loc,'ip':ip,'device':device,'channel':channel,'intl':intl,'risk':risk,'created':dt.isoformat().replace('+00:00','Z')})
        external_idx+=1
# Purpose-built edge cases to showcase risk signals and DBMS queries.
special_specs=[
 (account_ids[3],'Nova Electronics','E-commerce',184500,'ONLINE',1,96,'Singapore, SG',now-timedelta(hours=3,minutes=15),'HIGH_VALUE + CROSS_BORDER','Large cross-border purchase inconsistent with the account profile.'),
 (account_ids[6],'ATM Cash Withdrawal','ATM',68500,'ATM',0,81,'Mumbai, IN',now-timedelta(hours=2,minutes=20),'LARGE_TICKET + ATM_PATTERN','High-value cash withdrawal exceeds the configured monitoring threshold.'),
 (account_ids[12],'Skyline Airways','Travel',94600,'ONLINE',1,88,'London, GB',now-timedelta(hours=1,minutes=40),'LARGE_TICKET + CROSS_BORDER','High-value international travel purchase requires review.'),
 (account_ids[1],'ShopKart','E-commerce',52750,'ONLINE',0,73,'Chennai, IN',now-timedelta(hours=1,minutes=10),'LARGE_TICKET','Large ticket transaction above the INR 50,000 threshold.'),
 (account_ids[8],'PeerPay Transfer','Transfer',112000,'MOBILE',0,92,'Bengaluru, IN',now-timedelta(minutes=42),'HIGH_VALUE','High-value peer transfer requires confirmation.'),
 (account_ids[2],'Nova Electronics','E-commerce',12800,'ONLINE',1,76,'Dubai, AE',now-timedelta(minutes=12),'CROSS_BORDER','International online purchase from a new region.'),
 (account_ids[10],'Urban Thread','E-commerce',6400,'POS',0,51,'Hyderabad, IN',now-timedelta(minutes=7),'VELOCITY','Multiple purchases clustered into a short time window.'),
 (account_ids[10],'GizmoHub','E-commerce',7100,'ONLINE',0,57,'Hyderabad, IN',now-timedelta(minutes=4),'VELOCITY','Repeated spending pattern within a short time window.'),
 (account_ids[10],'Daily Market','E-commerce',5950,'POS',0,59,'Hyderabad, IN',now-timedelta(minutes=2),'VELOCITY','Repeated spending pattern within a short time window.'),
 (account_ids[10],'StreamVerse','Entertainment',2300,'ONLINE',0,45,'Hyderabad, IN',now-timedelta(minutes=1),'VELOCITY','Repeated spending pattern within a short time window.'),
 (account_ids[5],'Campus Fees Portal','Education',38500,'ONLINE',0,64,'Pune, IN',now-timedelta(hours=5),'LARGE_TICKET','Large education payment flagged for analyst review.'),
 (account_ids[14],'Metro Petrol','Fuel',3800,'POS',0,18,'Coimbatore, IN',now-timedelta(hours=6),'NONE','Normal low-risk payment.'),
 # Deliberately left without a seeded alert so the first live scan creates a new one.
 (account_ids[15],'Nova Electronics','E-commerce',135000,'ONLINE',0,12,'Pune, IN',now-timedelta(minutes=25),'HIGH_VALUE','Unreviewed high-value ecommerce transaction designed to be evaluated by the next threat scan.'),
]
special_tx_ids=[]
for spec in special_specs:
    aid,merchant,cat,amt,channel,intl,risk,loc,dt,rules,reason=spec
    # use explicit ids after randomized set
    tid=external_idx; external_idx+=1; special_tx_ids.append(tid)
    tx_type='WITHDRAWAL' if channel=='ATM' else 'TRANSFER' if cat=='Transfer' else 'PAYMENT'
    tx={'id':tid,'ref':f'PX-LIVE-{tid:05d}','account':aid,'counterparty':None,'merchant':merchant,'category':cat,'amount':float(amt),'currency':'INR','type':tx_type,'status':'COMPLETED','location':loc,'ip':f'198.51.100.{tid%200+1}' if intl else f'192.0.2.{tid%200+1}','device':f'DEV-{tid%14+1:03d}','channel':channel,'intl':intl,'risk':risk,'created':dt.isoformat().replace('+00:00','Z'),'rules':rules,'reason':reason}
    transactions.append(tx)

# Choose several existing events for a mixture of investigation outcomes.
alerts=[]
# special indices: open critical/high/medium; some settled/false positive for disposition reporting
alert_tx_plan=[
 (special_tx_ids[0],'CRITICAL',96,'HIGH_VALUE + CROSS_BORDER','Large cross-border purchase inconsistent with the account profile.','OPEN'),
 (special_tx_ids[1],'HIGH',81,'LARGE_TICKET + ATM_PATTERN','High-value cash withdrawal exceeds the configured monitoring threshold.','INVESTIGATING'),
 (special_tx_ids[2],'HIGH',88,'LARGE_TICKET + CROSS_BORDER','High-value international travel purchase requires review.','OPEN'),
 (special_tx_ids[3],'HIGH',73,'LARGE_TICKET','Large ticket transaction above the INR 50,000 threshold.','OPEN'),
 (special_tx_ids[4],'CRITICAL',92,'HIGH_VALUE','High-value peer transfer requires confirmation.','INVESTIGATING'),
 (special_tx_ids[5],'HIGH',76,'CROSS_BORDER','International online purchase from a new region.','OPEN'),
 (special_tx_ids[6],'MEDIUM',51,'VELOCITY','Multiple purchases clustered into a short time window.','OPEN'),
 (special_tx_ids[7],'MEDIUM',57,'VELOCITY','Repeated spending pattern within a short time window.','OPEN'),
 (special_tx_ids[8],'MEDIUM',59,'VELOCITY','Repeated spending pattern within a short time window.','OPEN'),
 (special_tx_ids[9],'MEDIUM',45,'VELOCITY','Repeated spending pattern within a short time window.','RESOLVED'),
 (special_tx_ids[10],'MEDIUM',64,'LARGE_TICKET','Large education payment flagged for analyst review.','FALSE_POSITIVE'),
]
for i,(tid,sev,score,rules,reason,status) in enumerate(alert_tx_plan,1):
    tx=next(x for x in transactions if x['id']==tid)
    created=tx['created']
    assigned='A. Sharma' if status=='INVESTIGATING' else ('Fraud Operations' if status in ('OPEN','RESOLVED') else 'M. Iyer')
    alerts.append((i,tid,tx['account'],sev,score,rules,reason,status,assigned,created,now.isoformat().replace('+00:00','Z')))

# Also include several lower-score historical investigations for a richer disposition table.
for idx,tx in enumerate([t for t in transactions if t['risk']>=65 and t['id'] not in special_tx_ids][:4],12):
    status=['RESOLVED','FALSE_POSITIVE','OPEN','RESOLVED'][idx-12]
    sev='HIGH' if tx['risk']>=70 else 'MEDIUM'
    alerts.append((idx,tx['id'],tx['account'],sev,tx['risk'],'MODEL_SCORE','Seeded demonstration alert from a historical elevated-risk transaction.',status,'Fraud Operations',tx['created'],now.isoformat().replace('+00:00','Z')))


def q(v):
    if v is None: return 'NULL'
    if isinstance(v,bool): return '1' if v else '0'
    if isinstance(v,(int,float)): return str(v)
    return "'"+str(v).replace("'","''")+"'"

def insert(table, columns, rows):
    out=[]
    for row in rows:
        out.append(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(q(x) for x in row)});")
    return '\n'.join(out)

parts=["-- PHANTOM fictional demo seed. Safe to reset and rerun after deleting data/phantom.db.","-- All names, email addresses, IP addresses, and transaction records are illustrative test data only.","BEGIN IMMEDIATE;", "DELETE FROM audit_logs;", "DELETE FROM fraud_alerts;", "DELETE FROM transactions;", "DELETE FROM accounts;", "DELETE FROM customers;"]
parts.append(insert('customers',['id','full_name','email','phone','risk_tier','created_at'],[(i,n,e,p,r,(now-timedelta(days=180)).isoformat().replace('+00:00','Z')) for i,n,e,p,r in customers]))
parts.append(insert('accounts',['id','customer_id','account_type','balance','currency','status','country','created_at'],[(aid,cid,typ,bal,cur,st,country,(now-timedelta(days=160)).isoformat().replace('+00:00','Z')) for aid,cid,typ,bal,cur,st,country in accounts]))
parts.append(insert('transactions',['id','external_ref','account_id','counterparty_account_id','merchant','category','amount','currency','transaction_type','status','location','ip_address','device_id','channel','is_international','risk_score','created_at'],[(t['id'],t['ref'],t['account'],t['counterparty'],t['merchant'],t['category'],t['amount'],t['currency'],t['type'],t['status'],t['location'],t['ip'],t['device'],t['channel'],t['intl'],t['risk'],t['created']) for t in transactions]))
parts.append(insert('fraud_alerts',['id','transaction_id','account_id','severity','score','rule_name','reason','status','assigned_to','created_at','updated_at'],alerts))
parts.append("INSERT INTO audit_logs(actor, action, entity_type, entity_id, details, ip_address, created_at) VALUES ('seed-loader','DEMO_DATA_LOADED','system','PHANTOM','Fictional demo dataset loaded for educational demonstration only','127.0.0.1',"+q(now.isoformat().replace('+00:00','Z'))+");")
parts.append('COMMIT;')
(ROOT/'seed.sql').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
print(f'Wrote {ROOT / "seed.sql"}: {len(customers)} customers, {len(accounts)} accounts, {len(transactions)} transactions, {len(alerts)} alerts')
