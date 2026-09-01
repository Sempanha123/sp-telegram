from __future__ import annotations

import argparse
from datetime import datetime, timezone

from .database import SessionLocal
from .services import LicenseService, seed_plans


def main():
    parser=argparse.ArgumentParser(description="SP Telegram license administrator CLI")
    sub=parser.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("seed-plans")
    p=sub.add_parser("create");p.add_argument("--plan",required=True);p.add_argument("--expires",required=True);p.add_argument("--customer")
    p=sub.add_parser("plan");p.add_argument("license_id");p.add_argument("plan")
    p=sub.add_parser("status");p.add_argument("license_id");p.add_argument("status",choices=["ACTIVE","SUSPENDED","REVOKED"]);p.add_argument("--reason")
    p=sub.add_parser("extend");p.add_argument("license_id");p.add_argument("--expires",required=True)
    args=parser.parse_args()
    with SessionLocal() as db:
        if args.cmd=="seed-plans":seed_plans(db);print("Plans synchronized.");return
        svc=LicenseService(db);lic=svc.repo.get_license(getattr(args,"license_id","") or "")
        if args.cmd=="create":
            lic,key=svc.create_license(args.plan,datetime.fromisoformat(args.expires.replace("Z","+00:00")),args.customer);print("LICENSE ID:",lic.id);print("LICENSE KEY (shown once):",key);return
        if not lic:raise SystemExit("License not found")
        if args.cmd=="plan":svc.set_plan(lic,args.plan);print("Plan:",lic.plan.code)
        elif args.cmd=="status":svc.set_status(lic,args.status,args.reason);print("Status:",lic.status)
        elif args.cmd=="extend":svc.set_expiry(lic,datetime.fromisoformat(args.expires.replace("Z","+00:00")));print("Expires:",lic.expires_at)

if __name__=="__main__":main()
