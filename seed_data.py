"""
AU Payroll Platform - Sample Data Seeder
========================================
Clears all existing data first, then inserts 100+ fresh records.

Usage:
    pip install requests
    python seed_data.py

Requirements:
    - Docker containers must be running (docker compose up)
"""

import requests, random, sys, subprocess
from datetime import date, timedelta
from typing import List, Any

BASE_URL       = "http://localhost:8000/api"
ADMIN_EMAIL    = "admin@payroll.com.au"
ADMIN_PASSWORD = "Admin1234!"

FIRST_NAMES = [
    "James","Oliver","William","Noah","Jack","Lucas","Henry","Mason","Ethan","Liam",
    "Charlotte","Olivia","Amelia","Isla","Mia","Ava","Grace","Sophie","Chloe","Emma",
    "Thomas","George","Edward","Harry","Samuel","Benjamin","Alexander","Daniel","Matthew","Joshua",
    "Emily","Sarah","Jessica","Rebecca","Lauren","Hannah","Natalie","Zoe","Isabella","Lily",
    "Michael","David","Andrew","Christopher","Ryan","Nathan","Jordan","Dylan","Callum","Lachlan",
    "Brooke","Taylah","Ashleigh","Brittany","Madison","Paige","Hayley","Courtney","Jade","Maddison",
    "Patrick","Sean","Brendan","Declan","Connor","Finn","Angus","Fraser","Hamish","Cameron",
    "Mei","Anh","Wei","Yuki","Priya","Anita","Raj","Arjun","Ahmed","Sara",
    "Maria","Elena","Marco","Luigi","Anna","Peter","Paul","Mark","Luke","John",
    "Simon","Adrian","Melissa","Vanessa","Nicole","Stephanie","Belinda","Robyn","Leanne","Tracey",
]
LAST_NAMES = [
    "Smith","Jones","Williams","Brown","Wilson","Taylor","Johnson","White","Martin","Anderson",
    "Thompson","Garcia","Martinez","Davis","Robinson","Clark","Rodriguez","Lewis","Lee","Walker",
    "Hall","Allen","Young","Hernandez","King","Wright","Lopez","Hill","Scott","Green",
    "Adams","Baker","Gonzalez","Nelson","Carter","Mitchell","Perez","Roberts","Turner","Phillips",
    "Campbell","Parker","Evans","Edwards","Collins","Stewart","Sanchez","Morris","Rogers","Reed",
    "Cook","Morgan","Bell","Murphy","Bailey","Rivera","Cooper","Richardson","Cox","Howard",
    "Ward","Torres","Peterson","Gray","Ramirez","James","Watson","Brooks","Kelly","Sanders",
    "Price","Bennett","Wood","Barnes","Ross","Henderson","Coleman","Jenkins","Perry","Powell",
    "Nguyen","Kim","Patel","Singh","Kumar","Chen","Wang","Liu","Zhang","Walsh",
    "Ryan","OConnor","McCarthy","Hughes","Flores","Butler","Simmons","Foster","Long","Hunt",
]
STATES   = ["NSW","VIC","QLD","WA","SA","TAS","ACT","NT"]
SUBURBS  = {
    "NSW":["Sydney","Parramatta","Chatswood","Bondi","Newtown","Surry Hills","Manly","Hornsby"],
    "VIC":["Melbourne","Richmond","St Kilda","Fitzroy","Hawthorn","Carlton","Dandenong","Geelong"],
    "QLD":["Brisbane","Gold Coast","Sunshine Coast","Toowoomba","Cairns","Townsville","Ipswich"],
    "WA": ["Perth","Fremantle","Joondalup","Rockingham","Mandurah","Bunbury"],
    "SA": ["Adelaide","Glenelg","Norwood","Unley","Prospect","Marion"],
    "TAS":["Hobart","Launceston","Devonport","Burnie"],
    "ACT":["Canberra","Belconnen","Tuggeranong","Gungahlin"],
    "NT": ["Darwin","Alice Springs","Palmerston"],
}
POSTCODES = {
    "NSW":["2000","2010","2020","2060","2100","2150","2200"],
    "VIC":["3000","3004","3050","3121","3141","3181","3220"],
    "QLD":["4000","4006","4101","4215","4550","4700","4810"],
    "WA": ["6000","6005","6100","6160","6210","6230"],
    "SA": ["5000","5006","5034","5038","5043","5067"],
    "TAS":["7000","7005","7010","7250","7310"],
    "ACT":["2600","2601","2602","2610","2615"],
    "NT": ["0800","0810","0820","0870"],
}
SUPER_FUNDS=[
    ("AustralianSuper","STA0100AU"),("Aware Super","WST0101AU"),
    ("UniSuper","UNI0100AU"),("Cbus Super","CBU0100AU"),
    ("REST Super","RES0100AU"),("HESTA","HES0100AU"),
    ("Sunsuper","SUN0100AU"),("MLC Super","MLC0100AU"),
    ("Colonial First State","CFS0100AU"),("BT Super","BTA0100AU"),
]
BANKS=[
    ("Commonwealth Bank","062-000"),("Westpac","032-000"),
    ("ANZ","012-000"),("NAB","083-000"),
    ("Bendigo Bank","633-000"),("Bank of Queensland","124-000"),
    ("Suncorp Bank","484-799"),("ING","923-100"),
]
EMP_TYPES   = ["full_time","full_time","full_time","part_time","part_time","casual","contract"]
PAY_FREQS   = ["fortnightly","fortnightly","fortnightly","monthly","weekly"]
SAL_RANGES  = {"full_time":(55000,180000),"part_time":(30000,95000),"casual":(25000,60000),"contract":(80000,220000)}
STREETS     = ["George","Pitt","Queen","King","Market","Collins","Bourke","Elizabeth","Victoria","Pacific Highway"]
LEAVE_REASONS=["Family vacation","Medical appointment","Personal matters","Holiday travel","Sick","Moving house","Wedding","Study leave","Mental health day",""]
TS_NOTES    =["Standard fortnight","Includes project overtime","Public holiday week","Annual leave taken","Sick day included","Normal hours",""]

def rdate(y0=2018,y1=2023):
    s=date(y0,1,1); return (s+timedelta(days=random.randint(0,(date(y1,12,31)-s).days))).strftime("%Y-%m-%d")
def tfn():    return f"{random.randint(100,999)}-{random.randint(100,999)}-{random.randint(100,999)}"
def phone():  return f"04{random.randint(10,99)} {random.randint(100,999)} {random.randint(100,999)}"
def acct():   return str(random.randint(100000000,999999999))
def em(f,l,i):
    d=random.choice(["gmail.com","outlook.com","yahoo.com.au","hotmail.com","icloud.com"])
    return f"{f.lower().replace(chr(39),'')}.{l.lower().replace(chr(39),'')}{i}@{d}"

def wipe_databases():
    print("  Truncating all tables...")
    tables={
        "employee_db":  ["users","employees"],
        "timesheet_db": ["leave_requests","timesheets"],
        "payroll_db":   ["audit_logs","payslips","payroll_runs"],
        "compliance_db":["payg_summaries","stp_submissions"],
        "payments_db":  ["payment_transactions","super_batches","payment_batches"],
        "reporting_db": ["reports"],
    }
    ok=0
    for db,tbls in tables.items():
        for tbl in tbls:
            cmd=["docker","exec","au-payroll-postgres","psql","-U","payroll","-d",db,"-c",f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE;"]
            try:
                r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
                if r.returncode==0: ok+=1
            except: pass
    print(f"  Cleared {ok} tables")

class Client:
    def __init__(self):
        self.s=requests.Session(); self.token=None
    def seed_admin(self):
        try: r=self.s.post(f"{BASE_URL}/auth/seed-admin",timeout=10); print(f"  {r.json().get('message','done')}")
        except Exception as e: print(f"  {e}")
    def login(self):
        try:
            r=self.s.post(f"{BASE_URL}/auth/login",json={"email":ADMIN_EMAIL,"password":ADMIN_PASSWORD},timeout=10)
            if r.status_code==200:
                self.token=r.json()["access_token"]; self.s.headers.update({"Authorization":f"Bearer {self.token}"}); print("  Login OK"); return True
            print(f"  Login failed: {r.text[:80]}"); return False
        except Exception as e: print(f"  Cannot connect: {e}\n  Run: docker compose up"); return False
    def post(self,path,data):
        try:
            r=self.s.post(f"{BASE_URL}{path}",json=data,timeout=15)
            return r.json() if r.status_code in(200,201) else {"error":r.text[:100]}
        except Exception as e: return {"error":str(e)}

def make_employees(n=100):
    emps,used_e=[],set()
    for i in range(1,n+1):
        f=random.choice(FIRST_NAMES); l=random.choice(LAST_NAMES)
        e=em(f,l,i)
        while e in used_e: e=em(f,l,random.randint(1000,9999))
        used_e.add(e)
        et=random.choice(EMP_TYPES); lo,hi=SAL_RANGES[et]; sal=round(random.randint(lo,hi)/1000)*1000
        st=random.choice(STATES); sf,usi=random.choice(SUPER_FUNDS); _,bsb=random.choice(BANKS)
        emps.append({
            "employee_number":f"E{i:04d}","first_name":f,"last_name":l,"email":e,"phone":phone(),"tfn":tfn(),
            "employment_type":et,"pay_frequency":random.choice(PAY_FREQS),"annual_salary":float(sal),
            "hourly_rate":round(sal/(52*38),2) if et=="casual" else None,
            "super_fund_name":sf,"super_fund_usi":usi,"super_member_number":f"MEM{random.randint(10000000,99999999)}",
            "bank_bsb":bsb,"bank_account_number":acct(),"bank_account_name":f"{f} {l}",
            "start_date":rdate(2018,2023),"tax_free_threshold":random.choice([True,True,True,False]),
            "residency_status":random.choice(["resident","resident","resident","non_resident"]),
            "address_line1":f"{random.randint(1,200)} {random.choice(STREETS)} Street",
            "address_suburb":random.choice(SUBURBS[st]),"address_state":st,"address_postcode":random.choice(POSTCODES[st]),
        })
    return emps

def make_timesheets(ids):
    periods=[("2024-01-01","2024-01-14"),("2024-01-15","2024-01-28"),("2024-01-29","2024-02-11"),
             ("2024-02-12","2024-02-25"),("2024-02-26","2024-03-10"),("2024-03-11","2024-03-24"),
             ("2024-03-25","2024-04-07"),("2024-04-08","2024-04-21")]
    sheets=[]
    for eid in ids:
        for ps,pe in random.sample(periods,3):
            sheets.append({
                "employee_id":eid,"period_start":ps,"period_end":pe,
                "ordinary_hours":round(random.uniform(60,80),1),
                "overtime_hours_1_5x":round(random.uniform(0,8),1) if random.random()>0.5 else 0,
                "overtime_hours_2x":round(random.uniform(0,4),1) if random.random()>0.8 else 0,
                "public_holiday_hours":round(random.uniform(0,7.6),1) if random.random()>0.85 else 0,
                "annual_leave_hours":round(random.uniform(0,15),1) if random.random()>0.8 else 0,
                "sick_leave_hours":round(random.uniform(0,7.6),1) if random.random()>0.85 else 0,
                "long_service_leave_hours":0,"unpaid_leave_hours":0,"notes":random.choice(TS_NOTES),
            })
    return sheets

def main():
    print(); print("="*60); print("   AU PAYROLL PLATFORM - SAMPLE DATA SEEDER"); print("="*60); print()
    client=Client()

    print("[0/6] Clearing all existing data...")
    wipe_databases(); print()

    print("[1/6] Setting up admin...")
    client.seed_admin()
    if not client.login(): sys.exit(1)
    print()

    print("[2/6] Creating 100 employees...")
    emp_data=make_employees(100); created=[]
    for i,e in enumerate(emp_data,1):
        r=client.post("/employees",e)
        if "id" in r: created.append(r)
        if i%20==0: print(f"  {i}/100...")
    print(f"  Created: {len(created)} employees"); print()

    if not created: print("ERROR: No employees created."); sys.exit(1)
    ids=[e["id"] for e in created]

    print("[3/6] Creating user accounts (first 30 employees)...")
    users=0
    for i,e in enumerate(created[:30]):
        r=client.post("/auth/register",{"email":e["email"],"password":"Employee1234!","role":"payroll_officer" if i<3 else "employee","employee_id":e["id"]})
        if "user_id" in r: users+=1
    print(f"  Created: {users} user accounts"); print()

    print("[4/6] Creating ~300 timesheets...")
    ts_data=make_timesheets(ids); created_ts=[]; approved=0
    for i,ts in enumerate(ts_data,1):
        r=client.post("/timesheets",ts)
        if "id" in r:
            created_ts.append(r); tid=r["id"]
            if random.random()>0.15:
                client.post(f"/timesheets/{tid}/submit",{})
                if random.random()>0.25: client.post(f"/timesheets/{tid}/approve",{}); approved+=1
        if i%75==0: print(f"  {i}/{len(ts_data)}...")
    print(f"  Created: {len(created_ts)} timesheets, {approved} approved"); print()

    print("[5/6] Creating 60 leave requests...")
    leaves=0
    for eid in random.sample(ids,min(60,len(ids))):
        lt=random.choice(["annual","sick","personal","long_service"])
        sd=rdate(2024,2024); sdt=date.fromisoformat(sd); days=random.randint(1,10); edt=sdt+timedelta(days=days)
        r=client.post("/leave-requests",{"employee_id":eid,"leave_type":lt,"start_date":sd,"end_date":edt.strftime("%Y-%m-%d"),"hours_requested":round(days*7.6,1),"reason":random.choice(LEAVE_REASONS)})
        if "id" in r: leaves+=1
    print(f"  Created: {leaves} leave requests"); print()

    print("[6/6] Triggering sample payroll run...")
    pr=client.post("/payroll-runs",{"run_name":"Sample Run - Jan 2024","period_start":"2024-01-15","period_end":"2024-01-28","pay_date":"2024-01-31","pay_frequency":"fortnightly"})
    print(f"  Payroll run: {pr.get('run_id','see logs')} — {pr.get('status','triggered')}"); print()

    print("="*60); print("   SEEDING COMPLETE!"); print("="*60); print()
    print(f"  Employees     : {len(created)}")
    print(f"  User accounts : {users}")
    print(f"  Timesheets    : {len(created_ts)} ({approved} approved)")
    print(f"  Leave requests: {leaves}")
    print(); print("  Browser : http://localhost:3000")
    print("  Login   : admin@payroll.com.au / Admin1234!")
    print("  Employee password: Employee1234!")
    print(); print("  Sample employee logins:")
    for e in created[:5]: print(f"    {e['email']}")
    print()

if __name__=="__main__":
    main()
