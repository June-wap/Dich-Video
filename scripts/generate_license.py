"""Admin/Seller tool to generate Ed25519-signed offline license keys for Voca Basic.

Usage:
    Interactive mode:
        python scripts/generate_license.py

    CLI mode:
        python scripts/generate_license.py --machine-id VB-78BC-1320-F15A-46DB --customer "Nguyen Van A" --type lifetime
        python scripts/generate_license.py --machine-id VB-78BC-1320-F15A-46DB --customer "Nguyen Van A" --days 30
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SCRIPT_DIR = Path(__file__).parent.resolve()
PRIVATE_KEY_PATH = SCRIPT_DIR / "seller_private_key.pem"


def _b64encode_clean(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def load_or_create_private_key() -> ed25519.Ed25519PrivateKey:
    if PRIVATE_KEY_PATH.is_file():
        pem_bytes = PRIVATE_KEY_PATH.read_bytes()
        return serialization.load_pem_private_key(pem_bytes, password=None)

    print(f"[!] Chuan bi khoi tao khoa Private Key moi tai: {PRIVATE_KEY_PATH}")
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pem_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIVATE_KEY_PATH.write_bytes(pem_bytes)
    pub_raw = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    print(f"[+] Da tao khoa moi! Public Key (Hex): {pub_raw.hex()}")
    print("[!] Chu y cap nhat PUBLIC_KEY_HEX trong backend/services/license_service.py!")
    return priv_key


def generate_license_key(
    private_key: ed25519.Ed25519PrivateKey,
    machine_id: str,
    customer_name: str,
    license_type: str = "lifetime",
    days: Optional[int] = None,
    hours: Optional[float] = None,
    expires_date_str: Optional[str] = None,
    is_trial: bool = False,
) -> str:
    now = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()

    expires_ts: Optional[float] = None
    if license_type == "time_limited":
        if hours is not None:
            expires_ts = now + (float(hours) * 3600)
        elif days is not None:
            expires_ts = now + (days * 86400)
        elif expires_date_str:
            dt = datetime.strptime(expires_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            expires_ts = dt.timestamp()
        else:
            raise ValueError("Time-limited license requires either 'hours', 'days', or 'expires_date_str'.")

    payload = {
        "v": 1,
        "m": machine_id.strip().upper(),
        "c": customer_name.strip(),
        "t": license_type,
        "i": now_iso,
    }
    if is_trial:
        payload["trial"] = True
    if expires_ts:
        payload["e"] = expires_ts

    # Canonical JSON serialization
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    # Sign using Ed25519
    signature = private_key.sign(payload_bytes)

    # Output: payload_b64.sig_b64
    payload_b64 = _b64encode_clean(payload_bytes)
    sig_b64 = _b64encode_clean(signature)
    return f"{payload_b64}.{sig_b64}"


def copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode("utf-8"))
            return p.returncode == 0
    except Exception:
        pass
    return False


def interactive_mode(priv_key: ed25519.Ed25519PrivateKey) -> None:
    print("\n" + "=" * 60)
    print("      VOCA BASIC - CONG CU TAO MA BAN QUYEN (KEYGEN)")
    print("=" * 60)

    # 1. Machine ID
    while True:
        mid = input("\n[1] Nhap Ma may cua khach (Machine ID, vd: VB-XXXX-XXXX-XXXX-XXXX): ").strip().upper()
        if mid.startswith("VB-") and len(mid) >= 15:
            break
        print("    [!] Ma may khong dung dinh dang (phai bat dau bang VB-). Vui long nhap lai!")

    # 2. Customer Name
    customer = input("[2] Nhap Ten khach hang: ").strip()
    if not customer:
        customer = "Khach Hang"

    # 3. License Type
    print("\n[3] Chon loai ban quyen:")
    print("    1. Vinh vien (Tron doi - Lifetime)")
    print("    2. Co thoi han (Theo so ngay su dung)")
    print("    3. Dung thu Trial (Theo gio, mac dinh 1 tieng)")
    choice = input("    Lua chon [1, 2 hoac 3, mac dinh la 1]: ").strip()

    lic_type = "lifetime"
    days = None
    hours = None
    is_trial = False

    if choice == "2":
        lic_type = "time_limited"
        while True:
            days_str = input("    Nhap so ngay cap ban quyen (vd: 30, 90, 365): ").strip()
            if days_str.isdigit() and int(days_str) > 0:
                days = int(days_str)
                break
            print("    [!] So ngay khong hop le. Vui long nhap so nguyen duong!")
    elif choice == "3":
        lic_type = "time_limited"
        is_trial = True
        hours_str = input("    Nhap so gio dung thu (vd: 1, 2, 24 - mac dinh: 1): ").strip()
        if hours_str and hours_str.replace(".", "", 1).isdigit() and float(hours_str) > 0:
            hours = float(hours_str)
        else:
            hours = 1.0

    # Sinh key
    key = generate_license_key(
        priv_key,
        machine_id=mid,
        customer_name=customer,
        license_type=lic_type,
        days=days,
        hours=hours,
        is_trial=is_trial,
    )

    # Luu ra file
    out_dir = SCRIPT_DIR / "licenses"
    out_dir.mkdir(exist_ok=True)
    safe_name = "".join(c for c in customer if c.isalnum() or c in (" ", "_", "-")).strip()
    file_path = out_dir / f"license_{safe_name}_{int(time.time())}.txt"

    if lic_type == "lifetime":
        expires_desc = "Vinh vien (Tron doi)"
    elif is_trial:
        expires_desc = f"Dung thu Trial ({hours:g} gio)"
    else:
        expires_desc = f"{days} ngay (ke tu hom nay)"
    summary = f"""======================================================
THONG TIN BAN QUYEN VOCA BASIC
======================================================
Khach hang: {customer}
Ma may (Machine ID): {mid}
Goi ban quyen: {expires_desc}
Ngay tao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

MA BAN QUYEN (LICENSE KEY):
------------------------------------------------------
{key}
------------------------------------------------------
Huong dan cho khach:
1. Mo ung dung Voca Basic
2. Vao Cai dat > Ban quyen (hoac bam nut 'Kich hoat ban quyen')
3. Dan ma tren vao o va bam 'Kich hoat ban quyen'.
======================================================
"""
    file_path.write_text(summary, encoding="utf-8")

    copied = copy_to_clipboard(key)

    print("\n" + "=" * 60)
    print(" TAO BAN QUYEN THANH CONG!")
    print("=" * 60)
    print(f"Khach hang: {customer}")
    print(f"Goi:        {expires_desc}")
    print(f"File luu:   {file_path}")
    if copied:
        print("[+] DA TU DONG SAO CHEP LICENSE KEY VAO CLIPBOARD (Bo nho tam)!")
        print("    Ban chi can nhan Ctrl + V de gui cho khach qua Zalo/Telegram.")
    print("\nLICENSE KEY:\n" + key + "\n")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Voca Basic Offline License Key Generator")
    parser.add_argument("--machine-id", type=str, help="Customer Machine ID (e.g. VB-XXXX-XXXX-XXXX-XXXX)")
    parser.add_argument("--customer", type=str, default="Customer", help="Customer name")
    parser.add_argument("--type", choices=["lifetime", "time_limited"], default="lifetime", help="License type")
    parser.add_argument("--days", type=int, help="Days of validity for time_limited license")
    parser.add_argument("--hours", type=float, help="Hours of validity for trial/time_limited license (e.g. 1)")
    parser.add_argument("--trial", action="store_true", help="Mark as trial license")
    parser.add_argument("--expires", type=str, help="Expiry date in YYYY-MM-DD")
    parser.add_argument("--init-keys", action="store_true", help="Generate and print master keypair")

    args = parser.parse_args()
    priv_key = load_or_create_private_key()

    if args.init_keys:
        pub_raw = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        print(f"Private Key Path: {PRIVATE_KEY_PATH}")
        print(f"Public Key Hex:   {pub_raw.hex()}")
        return

    if args.machine_id:
        lic_type = "time_limited" if (args.days or args.hours or args.expires or args.trial or args.type == "time_limited") else "lifetime"
        key = generate_license_key(
            priv_key,
            machine_id=args.machine_id,
            customer_name=args.customer,
            license_type=lic_type,
            days=args.days,
            hours=args.hours,
            expires_date_str=args.expires,
            is_trial=args.trial,
        )
        print(f"MACHINE_ID: {args.machine_id}")
        print(f"CUSTOMER:   {args.customer}")
        print(f"TYPE:       {lic_type}")
        print(f"KEY:        {key}")
        copy_to_clipboard(key)
    else:
        interactive_mode(priv_key)


if __name__ == "__main__":
    main()
