"""Cloud License V2 Administrator & Seller CLI Tool for Voca Basic.

Supports managing licenses on Firebase Cloud via Admin API or direct Firebase Admin SDK.
Never package this script or service account credentials into customer distributions!

Usage:
    Create a lifetime license:
        python scripts/cloud_license_admin.py create --customer "Nguyen Van A" --plan lifetime --max-devices 1

    Create a 30-day time-limited license:
        python scripts/cloud_license_admin.py create --customer "Tran Van B" --plan time_limited --days 30

    Block a license:
        python scripts/cloud_license_admin.py block --key VB-ABCD-EFGH-1234-5678-9999 --reason "Chargeback"

    Unblock a license:
        python scripts/cloud_license_admin.py unblock --key VB-ABCD-EFGH-1234-5678-9999

    Extend license expiration:
        python scripts/cloud_license_admin.py extend --key VB-ABCD-EFGH-1234-5678-9999 --days 30

    Revoke device activation:
        python scripts/cloud_license_admin.py revoke --key VB-ABCD-EFGH-1234-5678-9999 --machine-id VB-78BC-1320-F15A-46DB

    List activations for a license:
        python scripts/cloud_license_admin.py list --key VB-ABCD-EFGH-1234-5678-9999
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def get_admin_api_config():
    cloud_url = os.getenv("CLOUD_LICENSE_URL", "").rstrip("/")
    admin_key = os.getenv("ADMIN_API_KEY", "")
    return cloud_url, admin_key


def call_admin_api(endpoint: str, payload: dict) -> dict:
    cloud_url, admin_key = get_admin_api_config()
    if not cloud_url:
        print("[!] ERROR: Vui long dat bien moi truong CLOUD_LICENSE_URL")
        print("    Vi du: set CLOUD_LICENSE_URL=https://us-central1-your-project.cloudfunctions.net")
        sys.exit(1)
    if not admin_key:
        print("[!] ERROR: Vui long dat bien moi truong ADMIN_API_KEY")
        print("    Vi du: set ADMIN_API_KEY=your-admin-secret-key")
        sys.exit(1)

    full_url = f"{cloud_url}/{endpoint.lstrip('/')}"
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        full_url,
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": admin_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        try:
            return json.loads(err_body)
        except Exception:
            return {"ok": False, "status": exc.code, "message": err_body}
    except Exception as exc:
        return {"ok": False, "message": f"Connection error: {exc}"}


def cmd_create(args):
    payload = {
        "customerId": args.customer,
        "plan": args.plan,
        "maxDevices": args.max_devices,
        "days": args.days,
        "notes": args.notes or "",
    }
    print(f"[*] Dang tao License tren Cloud: {payload['customerId']} ({payload['plan']})...")
    res = call_admin_api("adminCreateLicense", payload)
    if res.get("ok"):
        print("\n" + "=" * 60)
        print("   TAO CLOUD LICENSE THANH CONG!")
        print("=" * 60)
        print(f"License Key:    {res.get('licenseKey')}")
        print(f"License Hash:   {res.get('licenseHash')}")
        print(f"Khach hang:     {res.get('customerId')}")
        print(f"Goi:            {res.get('plan')}")
        print(f"So may toi da:  {res.get('maxDevices')}")
        print(f"Ngay het han:   {res.get('expiresAt') or 'Vinh vien'}")
        print("=" * 60)
        print("\n[!] LUU Y: Plaintext License Key chi hien thi duy nhat mot lan luc nay.")
        print("    Hay sao chep va gui key tren cho khach hang!\n")
    else:
        print(f"[!] That bai: {res.get('message') or res}")


def cmd_block(args):
    res = call_admin_api("adminBlockLicense", {"licenseKeyOrHash": args.key, "reason": args.reason or "Admin blocked"})
    if res.get("ok"):
        print(f"[+] Da khoa license {args.key} thanh cong.")
    else:
        print(f"[!] That bai: {res}")


def cmd_unblock(args):
    res = call_admin_api("adminUnblockLicense", {"licenseKeyOrHash": args.key})
    if res.get("ok"):
        print(f"[+] Da mo khoa license {args.key} thanh cong.")
    else:
        print(f"[!] That bai: {res}")


def cmd_extend(args):
    res = call_admin_api("adminExtendLicense", {"licenseKeyOrHash": args.key, "additionalDays": args.days})
    if res.get("ok"):
        print(f"[+] Da gia han {args.days} ngay cho license {args.key}. Han moi: {res.get('newExpiresAt')}")
    else:
        print(f"[!] That bai: {res}")


def cmd_revoke(args):
    res = call_admin_api("adminRevokeActivation", {"licenseKeyOrHash": args.key, "machineId": args.machine_id})
    if res.get("ok"):
        print(f"[+] Da thu hoi kich hoat cua may {args.machine_id} tren license {args.key}.")
    else:
        print(f"[!] That bai: {res}")


def cmd_list(args):
    res = call_admin_api("adminListActivations", {"licenseKeyOrHash": args.key})
    if res.get("ok"):
        activations = res.get("activations", [])
        print(f"\nDanh sach thiet bi da kich hoat ({len(activations)} may):")
        for idx, act in enumerate(activations, 1):
            print(f"  {idx}. Machine Hash: {act.get('machineIdHash')} | Trang thai: {act.get('status')} | Phien ban token: {act.get('tokenVersion')}")
    else:
        print(f"[!] That bai: {res}")


def main():
    parser = argparse.ArgumentParser(description="Voca Basic Cloud License Admin CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # create
    p_create = subparsers.add_parser("create", help="Tao license moi")
    p_create.add_argument("--customer", required=True, help="Ten khach hang")
    p_create.add_argument("--plan", choices=["lifetime", "time_limited"], default="lifetime", help="Goi ban quyen")
    p_create.add_argument("--max-devices", type=int, default=1, help="So luong thiet bi toi da")
    p_create.add_argument("--days", type=int, default=30, help="So ngay su dung (neu time_limited)")
    p_create.add_argument("--notes", help="Ghi chu them")
    p_create.set_defaults(func=cmd_create)

    # block
    p_block = subparsers.add_parser("block", help="Khoa license")
    p_block.add_argument("--key", required=True, help="License key hoac license hash")
    p_block.add_argument("--reason", help="Ly do khoa")
    p_block.set_defaults(func=cmd_block)

    # unblock
    p_unblock = subparsers.add_parser("unblock", help="Mo khoa license")
    p_unblock.add_argument("--key", required=True, help="License key hoac license hash")
    p_unblock.set_defaults(func=cmd_unblock)

    # extend
    p_extend = subparsers.add_parser("extend", help="Gia han license")
    p_extend.add_argument("--key", required=True, help="License key hoac license hash")
    p_extend.add_argument("--days", type=int, required=True, help="So ngay gia han them")
    p_extend.set_defaults(func=cmd_extend)

    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Thu hoi kich hoat cua 1 thiet bi")
    p_revoke.add_argument("--key", required=True, help="License key hoac license hash")
    p_revoke.add_argument("--machine-id", required=True, help="Machine ID cua thiet bi can thu hoi")
    p_revoke.set_defaults(func=cmd_revoke)

    # list
    p_list = subparsers.add_parser("list", help="Liet ke thiet bi da kich hoat")
    p_list.add_argument("--key", required=True, help="License key hoac license hash")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
