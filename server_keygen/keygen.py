"""server_keygen/keygen.py — Cong cu Admin quan tri va tao License Key tren Firebase Cloud Firestore.

Dua tren mo hinh cua azure-viking, tich hop bao mat chuan Voca Basic V2:
- Tuong tac truc tiep voi Firebase Cloud Firestore thong qua firebase-admin SDK.
- Su dung serviceAccountKey.json (Chi nguoi ban nam giu, tuyet doi khong package vao app).
- Tu dong sinh key CSPRNG, tinh hash SHA-256 va day len Firestore.
- Ho tro ca dong lenh CLI va Menu tuong tac tieng Viet truc quan.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import secrets
import string
import subprocess
import sys
from typing import Optional

SCRIPT_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT_FILE = SCRIPT_DIR / "serviceAccountKey.json"
COLLECTION_LICENSES = "licenses"
COLLECTION_ACTIVATIONS = "activations"
COLLECTION_AUDIT = "auditLogs"

# Loai bo cac ky tu de nham lan: 0, O, 1, I, S, 5, Z, 2
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ346789"


def copy_to_clipboard(text: str) -> bool:
    """Sao chep chuoi vao Clipboard tren Windows."""
    try:
        if sys.platform == "win32":
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode("utf-8"))
            return p.returncode == 0
    except Exception:
        pass
    return False


def _init_firebase():
    """Khoi tao ket noi Firebase Admin SDK."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        print("\n[ERROR] Thieu thu vien firebase-admin!")
        print("-> Vui long chay lenh: pip install firebase-admin")
        print("   (Hoac dung .venv cua du an: ..\\.venv312\\Scripts\\pip install firebase-admin)\n")
        sys.exit(1)

    if not SERVICE_ACCOUNT_FILE.exists():
        print("\n" + "=" * 70)
        print("[!] CHUA CAU HINH FIREBASE SERVICE ACCOUNT KEY!")
        print("=" * 70)
        print(f"Khong tim thay file: {SERVICE_ACCOUNT_FILE}")
        print("\nHUONG DAN:")
        print("1. Truy cap: https://console.firebase.google.com (Chon project 'vocaltts')")
        print("2. Vao Project settings -> Tab 'Service accounts'")
        print("3. Bam 'Generate new private key' de tai file JSON")
        print(f"4. Luu va doi ten file thanh: serviceAccountKey.json vao thu muc:")
        print(f"   {SCRIPT_DIR}")
        print("=" * 70 + "\n")
        sys.exit(1)

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_FILE))
        firebase_admin.initialize_app(cred)

    return firestore.client()


def generate_license_key() -> str:
    """Sinh License Key CSPRNG dinh dang: VB-XXXX-XXXX-XXXX-XXXX-XXXX."""
    groups = []
    for _ in range(5):
        seg = "".join(secrets.choice(KEY_ALPHABET) for _ in range(4))
        groups.append(seg)
    return f"VB-{'-'.join(groups)}"


def normalize_key(key: str) -> str:
    return key.strip().upper()


def hash_key(normalized_key: str) -> str:
    return hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()


# ================================================================
# CAC LENH QUAN TRI (COMMANDS)
# ================================================================

def cmd_generate(args: argparse.Namespace) -> None:
    db = _init_firebase()
    plan = args.plan
    customer = (args.customer or "Khách hàng").strip()
    count = max(1, getattr(args, "count", 1))
    max_devices = max(1, getattr(args, "max_devices", 1))
    note = getattr(args, "note", "")

    expires_dt: Optional[datetime] = None
    days = getattr(args, "days", None)

    if plan == "time_limited":
        days_num = int(days) if days else 30
        expires_dt = datetime.now(timezone.utc) + timedelta(days=days_num)

    from firebase_admin import firestore

    generated_keys = []

    print(f"\n[*] Dang tao va day {count} license len Firebase Cloud Firestore...")
    col_ref = db.collection(COLLECTION_LICENSES)
    audit_ref = db.collection(COLLECTION_AUDIT)

    for i in range(count):
        raw_key = generate_license_key()
        norm = normalize_key(raw_key)
        lic_hash = hash_key(norm)

        payload = {
            "status": "active",
            "plan": plan,
            "maxDevices": max_devices,
            "activationCount": 0,
            "customerId": customer,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "expiresAt": expires_dt,
            "metadata": {
                "product": "voca-basic",
                "version": 2,
                "notes": note,
            },
        }

        col_ref.document(lic_hash).set(payload)

        # Audit log
        audit_ref.add({
            "event": "LICENSE_CREATED",
            "licenseHash": lic_hash,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "metadata": {
                "plan": plan,
                "maxDevices": max_devices,
                "customer": customer,
            },
        })

        generated_keys.append(raw_key)
        exp_desc = expires_dt.strftime("%d/%m/%Y") if expires_dt else "Vĩnh viễn (Lifetime)"
        print(f"  [{i+1:02d}] {raw_key}  |  Gói: {plan.upper()} ({exp_desc})  |  Khách: {customer}")

    if count == 1:
        copy_to_clipboard(generated_keys[0])
        print("\n" + "=" * 60)
        print("  TAO BAN QUYEN CLOUD THANH CONG!")
        print("=" * 60)
        print(f"LICENSE KEY:  {generated_keys[0]}")
        print(f"KHACH HANG:   {customer}")
        print(f"GOI:          {plan.upper()} (Tối đa {max_devices} máy)")
        print(f"HET HAN:      {expires_dt.strftime('%d/%m/%Y') if expires_dt else 'Vĩnh viễn (Lifetime)'}")
        print("=" * 60)
        print("[+] DA TU DONG SAO CHEP LICENSE KEY VAO CLIPBOARD (Bo nho tam)!")
        print("    Ban chi can nhan Ctrl + V de gui cho khach qua Zalo/Telegram.\n")
    else:
        print(f"\n[OK] Da tao thanh cong {count} keys va luu len Firebase Cloud.")


def cmd_list(args: argparse.Namespace) -> None:
    db = _init_firebase()
    print("\n[*] Dang tai danh sach ban quyen tu Cloud Firestore...")
    docs = db.collection(COLLECTION_LICENSES).stream()

    rows = []
    for doc in docs:
        d = doc.to_dict()
        lic_id = doc.id[:12] + "..."
        cust = str(d.get("customerId", "Khách"))[:20]
        plan = str(d.get("plan", "lifetime")).upper()
        status = str(d.get("status", "active")).upper()
        count = d.get("activationCount", 0)
        max_d = d.get("maxDevices", 1)
        devices_str = f"{count}/{max_d}"

        exp = d.get("expiresAt")
        if exp:
            try:
                exp_str = exp.strftime("%d/%m/%Y")
            except Exception:
                exp_str = str(exp)[:10]
        else:
            exp_str = "Vĩnh viễn"

        notes = str(d.get("metadata", {}).get("notes", ""))[:15]
        rows.append((lic_id, cust, plan, status, devices_str, exp_str, notes))

    print("\n" + "=" * 96)
    print(f"{'HASH ID':<16} {'KHACH HANG':<22} {'GOI':<12} {'TRANG THAI':<12} {'MAY':<8} {'HET HAN':<14} GHI CHU")
    print("-" * 96)
    for r in rows:
        print(f"{r[0]:<16} {r[1]:<22} {r[2]:<12} {r[3]:<12} {r[4]:<8} {r[5]:<14} {r[6]}")
    print("=" * 96)
    print(f"Tong so: {len(rows)} licenses tren Cloud.\n")


def cmd_info(args: argparse.Namespace) -> None:
    db = _init_firebase()
    raw = args.key.strip()
    norm = normalize_key(raw)
    lic_hash = hash_key(norm) if norm.startswith("VB-") else norm

    doc = db.collection(COLLECTION_LICENSES).document(lic_hash).get()
    if not doc.exists:
        print(f"\n[!] Khong tim thay License tren Firestore (Hash: {lic_hash})\n")
        return

    d = doc.to_dict()
    print("\n" + "=" * 60)
    print("           THONG TIN CHI TIET LICENSE")
    print("=" * 60)
    print(f"License Hash:    {lic_hash}")
    print(f"Khach hang:      {d.get('customerId')}")
    print(f"Goi ban quyen:   {d.get('plan')}")
    print(f"Trang thai:      {d.get('status')}")
    print(f"So may da dung:  {d.get('activationCount', 0)} / {d.get('maxDevices', 1)}")

    exp = d.get("expiresAt")
    print(f"Ngay het han:    {exp.strftime('%d/%m/%Y %H:%M:%S') if exp else 'Vinh vien'}")
    print(f"Ghi chu:         {d.get('metadata', {}).get('notes', '')}")

    # Lay danh sach activations
    from google.cloud.firestore_v1.base_query import FieldFilter
    acts = db.collection(COLLECTION_ACTIVATIONS).where(filter=FieldFilter("licenseHash", "==", lic_hash)).stream()
    act_list = list(acts)
    print("\nDanh sach thiet bi dang kich hoat:")
    if not act_list:
        print("  (Chua co may nao kich hoat)")
    else:
        for idx, act in enumerate(act_list, 1):
            ad = act.to_dict()
            print(f"  [{idx}] Machine Hash: {ad.get('machineIdHash')[:16]}... | Status: {ad.get('status')} | Version: {ad.get('tokenVersion')}")
    print("=" * 60 + "\n")


def cmd_block(args: argparse.Namespace) -> None:
    db = _init_firebase()
    from firebase_admin import firestore
    raw = args.key.strip()
    norm = normalize_key(raw)
    lic_hash = hash_key(norm) if norm.startswith("VB-") else norm

    ref = db.collection(COLLECTION_LICENSES).document(lic_hash)
    if not ref.get().exists:
        print(f"\n[!] Khong tim thay license: {raw}\n")
        return

    reason = getattr(args, "reason", "Admin blocked") or "Admin blocked"
    ref.update({
        "status": "blocked",
        "metadata.blockedReason": reason,
        "metadata.blockedAt": firestore.SERVER_TIMESTAMP,
    })

    db.collection(COLLECTION_AUDIT).add({
        "event": "LICENSE_BLOCKED",
        "licenseHash": lic_hash,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "metadata": {"reason": reason},
    })
    print(f"\n[+] DA KHOA LICENSE THANH CONG! (Hash: {lic_hash[:16]}...)\n")


def cmd_unblock(args: argparse.Namespace) -> None:
    db = _init_firebase()
    from firebase_admin import firestore
    raw = args.key.strip()
    norm = normalize_key(raw)
    lic_hash = hash_key(norm) if norm.startswith("VB-") else norm

    ref = db.collection(COLLECTION_LICENSES).document(lic_hash)
    if not ref.get().exists:
        print(f"\n[!] Khong tim thay license: {raw}\n")
        return

    ref.update({
        "status": "active",
        "metadata.unblockedAt": firestore.SERVER_TIMESTAMP,
    })

    db.collection(COLLECTION_AUDIT).add({
        "event": "LICENSE_UNBLOCKED",
        "licenseHash": lic_hash,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })
    print(f"\n[+] DA MO KHOA LICENSE THANH CONG! (Hash: {lic_hash[:16]}...)\n")


def cmd_extend(args: argparse.Namespace) -> None:
    db = _init_firebase()
    from firebase_admin import firestore
    raw = args.key.strip()
    norm = normalize_key(raw)
    lic_hash = hash_key(norm) if norm.startswith("VB-") else norm

    ref = db.collection(COLLECTION_LICENSES).document(lic_hash)
    snap = ref.get()
    if not snap.exists:
        print(f"\n[!] Khong tim thay license: {raw}\n")
        return

    data = snap.to_dict()
    current_exp = data.get("expiresAt")
    now_utc = datetime.now(timezone.utc)

    if current_exp:
        base_time = max(now_utc, current_exp)
    else:
        base_time = now_utc

    days = int(args.days)
    new_exp = base_time + timedelta(days=days)

    ref.update({
        "status": "active",
        "plan": "time_limited",
        "expiresAt": new_exp,
    })

    db.collection(COLLECTION_AUDIT).add({
        "event": "LICENSE_EXTENDED",
        "licenseHash": lic_hash,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "metadata": {"addedDays": days, "newExpiresAt": new_exp.isoformat()},
    })
    print(f"\n[+] DA GIA HAN {days} NGAY! Han su dung moi: {new_exp.strftime('%d/%m/%Y %H:%M')}\n")


def cmd_reset_device(args: argparse.Namespace) -> None:
    db = _init_firebase()
    from firebase_admin import firestore
    raw = args.key.strip()
    norm = normalize_key(raw)
    lic_hash = hash_key(norm) if norm.startswith("VB-") else norm

    ref = db.collection(COLLECTION_LICENSES).document(lic_hash)
    if not ref.get().exists:
        print(f"\n[!] Khong tim thay license: {raw}\n")
        return

    # Xoa / danh dau revoked toan bo activation cu
    from google.cloud.firestore_v1.base_query import FieldFilter
    acts = db.collection(COLLECTION_ACTIVATIONS).where(filter=FieldFilter("licenseHash", "==", lic_hash)).stream()
    count_reset = 0
    for act in acts:
        act.reference.update({
            "status": "revoked",
            "revokedAt": firestore.SERVER_TIMESTAMP,
        })
        count_reset += 1

    # Reset so may dang dung ve 0
    ref.update({"activationCount": 0})

    db.collection(COLLECTION_AUDIT).add({
        "event": "DEVICE_RESET_ALL",
        "licenseHash": lic_hash,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "metadata": {"resetCount": count_reset},
    })

    print(f"\n[+] DA RESET {count_reset} THIET BI THANH CONG!")
    print(f"    Khach hang co the dung key nay de kich hoat tren may moi.\n")


# ================================================================
# INTERACTIVE MENU (KHI CHAY TRUC TIEP KHONG THAM SO)
# ================================================================

def interactive_menu():
    while True:
        print("\n" + "=" * 60)
        print("     VOCA BASIC - QUAN LY BAN QUYEN FIREBASE CLOUD")
        print("=" * 60)
        print(" [1] Tao License Key moi (Lifetime / Theo ngay)")
        print(" [2] Xem danh sach tat ca License tren Cloud")
        print(" [3] Xem chi tiet 1 License (thiet bi dang dung)")
        print(" [4] Khoa License (Block / Thu hoi)")
        print(" [5] Mo khoa License (Unblock)")
        print(" [6] Gia han License (Cong them so ngay)")
        print(" [7] Reset thiet bi (Cho phep khach doi sang may khac)")
        print(" [0] Thoat")
        print("=" * 60)

        choice = input(" Nhap lua chon [0-7]: ").strip()

        if choice == "0":
            print("\nTam biet!")
            break
        elif choice == "1":
            cust = input(" -> Nhap ten khach hang: ").strip() or "Khach Hang"
            print(" -> Chon goi ban quyen:")
            print("    1. Vinh vien (Lifetime)")
            print("    2. Theo so ngay (Time-limited)")
            p_ch = input("    Chon [1 hoac 2, mac dinh 1]: ").strip()
            if p_ch == "2":
                plan = "time_limited"
                days_str = input("    Nhap so ngay su dung (vd: 30, 90, 365): ").strip()
                days = int(days_str) if days_str.isdigit() else 30
            else:
                plan = "lifetime"
                days = None

            max_d_str = input(" -> So luong may duoc phep kich hoat (mac dinh 1): ").strip()
            max_d = int(max_d_str) if max_d_str.isdigit() else 1

            note = input(" -> Ghi chu (tuy chon): ").strip()

            args = argparse.Namespace(plan=plan, customer=cust, days=days, max_devices=max_d, count=1, note=note)
            cmd_generate(args)

        elif choice == "2":
            cmd_list(argparse.Namespace())
        elif choice == "3":
            k = input(" -> Nhap License Key (hoac Hash ID): ").strip()
            if k:
                cmd_info(argparse.Namespace(key=k))
        elif choice == "4":
            k = input(" -> Nhap License Key can KHOA: ").strip()
            if k:
                r = input(" -> Ly do khoa (vd: Het han, Gian lan): ").strip()
                cmd_block(argparse.Namespace(key=k, reason=r))
        elif choice == "5":
            k = input(" -> Nhap License Key can MO KHOA: ").strip()
            if k:
                cmd_unblock(argparse.Namespace(key=k))
        elif choice == "6":
            k = input(" -> Nhap License Key can GIA HAN: ").strip()
            if k:
                d = input(" -> Nhap so ngay can cong them: ").strip()
                if d.isdigit():
                    cmd_extend(argparse.Namespace(key=k, days=int(d)))
        elif choice == "7":
            k = input(" -> Nhap License Key can RESET THIET BI: ").strip()
            if k:
                cmd_reset_device(argparse.Namespace(key=k))

        input("\n[Nhan Enter de tiep tuc...]")


# ================================================================
# MAIN ENTRY POINT
# ================================================================

def main():
    parser = argparse.ArgumentParser(description="Voca Basic Firebase License Manager")
    sub = parser.add_subparsers(dest="command")

    p_gen = sub.add_parser("generate", help="Tao license moi")
    p_gen.add_argument("--plan", choices=["lifetime", "time_limited"], default="lifetime")
    p_gen.add_argument("--customer", default="Khách hàng")
    p_gen.add_argument("--days", type=int, default=30)
    p_gen.add_argument("--max-devices", type=int, default=1)
    p_gen.add_argument("--count", type=int, default=1)
    p_gen.add_argument("--note", default="")

    sub.add_parser("list", help="Xem danh sach license")

    p_info = sub.add_parser("info", help="Xem chi tiet license")
    p_info.add_argument("--key", required=True)

    p_blk = sub.add_parser("block", help="Khoa license")
    p_blk.add_argument("--key", required=True)
    p_blk.add_argument("--reason", default="Admin blocked")

    p_unblk = sub.add_parser("unblock", help="Mo khoa license")
    p_unblk.add_argument("--key", required=True)

    p_ext = sub.add_parser("extend", help="Gia han license")
    p_ext.add_argument("--key", required=True)
    p_ext.add_argument("--days", type=int, required=True)

    p_rst = sub.add_parser("reset-device", help="Reset thiet bi")
    p_rst.add_argument("--key", required=True)

    args = parser.parse_args()

    if not args.command:
        interactive_menu()
    else:
        cmds = {
            "generate": cmd_generate,
            "list": cmd_list,
            "info": cmd_info,
            "block": cmd_block,
            "unblock": cmd_unblock,
            "extend": cmd_extend,
            "reset-device": cmd_reset_device,
        }
        cmds[args.command](args)


if __name__ == "__main__":
    main()
