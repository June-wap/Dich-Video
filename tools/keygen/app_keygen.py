"""Voca Basic - Dedicated Standalone License Key Generator (GUI).
Built for the Seller/Admin with modern Tkinter/TTK.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def _b64encode_clean(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def get_private_key_path() -> Path:
    # 1. If running inside PyInstaller bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "seller_private_key.pem"
        if bundled.is_file():
            return bundled

    # 2. Candidate paths in repository
    here = Path(__file__).resolve().parent
    candidates = [
        here / "seller_private_key.pem",
        here.parent.parent / "scripts" / "seller_private_key.pem",
        Path.cwd() / "scripts" / "seller_private_key.pem",
        Path.cwd() / "seller_private_key.pem",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return here / "seller_private_key.pem"


def load_private_key() -> ed25519.Ed25519PrivateKey:
    path = get_private_key_path()
    if path.is_file():
        pem_bytes = path.read_bytes()
        return serialization.load_pem_private_key(pem_bytes, password=None)

    # If missing, generate new keypair and save
    path.parent.mkdir(parents=True, exist_ok=True)
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pem_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem_bytes)
    return priv_key


def generate_key_string(
    private_key: ed25519.Ed25519PrivateKey,
    machine_id: str,
    customer_name: str,
    license_type: str = "lifetime",
    days: int | None = None,
    hours: float | None = None,
    is_trial: bool = False,
) -> str:
    now = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()

    expires_ts: float | None = None
    if license_type == "time_limited":
        if hours is not None:
            expires_ts = now + (float(hours) * 3600)
        elif days is not None:
            expires_ts = now + (days * 86400)
        else:
            raise ValueError("Cần cung cấp số ngày hoặc số giờ.")

    payload = {
        "v": 1,
        "m": machine_id.strip().upper(),
        "c": customer_name.strip() or "Khách Hàng",
        "t": license_type,
        "i": now_iso,
    }
    if is_trial:
        payload["trial"] = True
    if expires_ts:
        payload["e"] = expires_ts

    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = private_key.sign(payload_bytes)

    payload_b64 = _b64encode_clean(payload_bytes)
    sig_b64 = _b64encode_clean(signature)
    return f"{payload_b64}.{sig_b64}"


def get_licenses_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent.parent
    d = base / "scripts" / "licenses"
    d.mkdir(parents=True, exist_ok=True)
    return d


class KeygenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Voca Basic - Bộ Quản Lý & Tạo Mã Bản Quyền")
        self.geometry("680x760")
        self.minsize(640, 720)

        # Set app icon if available
        self._set_icon()

        # Load cryptography key
        try:
            self.priv_key = load_private_key()
            self.key_status_text = "Khóa ký Ed25519: Sẵn sàng"
        except Exception as e:
            self.priv_key = None
            self.key_status_text = f"Lỗi nạp khóa: {e}"

        self.configure(bg="#f1f5f9")
        self._setup_styles()
        self._build_ui()

    def _set_icon(self):
        try:
            candidates = []
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                candidates.append(Path(sys._MEIPASS) / "icon.ico")
                candidates.append(Path(sys._MEIPASS) / "release" / "icon.ico")
            here = Path(__file__).resolve().parent
            candidates.extend([
                here.parent.parent / "release" / "icon.ico",
                Path.cwd() / "release" / "icon.ico",
                Path.cwd() / "icon.ico",
            ])
            for p in candidates:
                if p and p.is_file():
                    self.iconbitmap(str(p))
                    break
        except Exception:
            pass

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 10), background="#f1f5f9")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Header.TFrame", background="#1e293b")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), background="#16a34a", foreground="#ffffff")
        style.map("Success.TButton", background=[("active", "#15803d")])

    def _build_ui(self):
        # 1. Header Banner
        header = tk.Frame(self, bg="#1e293b", height=75)
        header.pack(fill="x", side="top")

        title_lbl = tk.Label(
            header,
            text="VOCA BASIC — BỘ TẠO MÃ BẢN QUYỀN",
            font=("Segoe UI", 15, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
        )
        title_lbl.pack(anchor="w", padx=24, pady=(12, 2))

        sub_lbl = tk.Label(
            header,
            text="Công cụ Quản trị viên • Ký số bảo mật Ed25519 • Cấp vĩnh viễn / ngày / trial 1 tiếng",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#94a3b8",
        )
        sub_lbl.pack(anchor="w", padx=24, pady=(0, 12))

        # Main Container
        container = tk.Frame(self, bg="#f1f5f9", padx=20, pady=16)
        container.pack(fill="both", expand=True)

        # 2. Form Card
        form_card = tk.Frame(container, bg="#ffffff", bd=1, relief="solid", highlightthickness=0)
        form_card.config(highlightbackground="#e2e8f0")
        form_card.pack(fill="x", pady=(0, 14), ipadx=14, ipady=14)

        # Machine ID Field
        mid_label_frame = tk.Frame(form_card, bg="#ffffff")
        mid_label_frame.pack(fill="x", padx=14, pady=(0, 4))

        tk.Label(
            mid_label_frame,
            text="1. Mã máy của khách (Machine ID):",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#1e293b",
        ).pack(side="left")

        mid_input_frame = tk.Frame(form_card, bg="#ffffff")
        mid_input_frame.pack(fill="x", padx=14, pady=(0, 12))

        self.mid_var = tk.StringVar()
        self.mid_var.trace_add("write", self._on_mid_change)

        self.mid_entry = tk.Entry(
            mid_input_frame,
            textvariable=self.mid_var,
            font=("Consolas", 12, "bold"),
            bg="#f8fafc",
            fg="#1d4ed8",
            relief="solid",
            bd=1,
        )
        self.mid_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

        paste_btn = tk.Button(
            mid_input_frame,
            text="📋 Dán từ Clipboard",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            cursor="hand2",
            padx=10,
            command=self._paste_clipboard,
        )
        paste_btn.pack(side="right", fill="y")

        self.mid_hint = tk.Label(
            form_card,
            text="Định dạng chuẩn: VB-XXXX-XXXX-XXXX-XXXX (Khách lấy từ ứng dụng Voca Basic)",
            font=("Segoe UI", 8),
            bg="#ffffff",
            fg="#64748b",
        )
        self.mid_hint.pack(anchor="w", padx=14, pady=(0, 10))

        # Customer Name Field
        tk.Label(
            form_card,
            text="2. Tên khách hàng (Customer Name):",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#1e293b",
        ).pack(anchor="w", padx=14, pady=(0, 4))

        self.cust_var = tk.StringVar(value="Khách Hàng")
        self.cust_entry = tk.Entry(
            form_card,
            textvariable=self.cust_var,
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg="#0f172a",
            relief="solid",
            bd=1,
        )
        self.cust_entry.pack(fill="x", padx=14, ipady=4, pady=(0, 14))

        # License Type Selection
        tk.Label(
            form_card,
            text="3. Chọn gói bản quyền cấp cho khách:",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#1e293b",
        ).pack(anchor="w", padx=14, pady=(0, 6))

        self.plan_var = tk.StringVar(value="trial_1h")

        plan_frame = tk.Frame(form_card, bg="#ffffff")
        plan_frame.pack(fill="x", padx=14, pady=(0, 10))

        # Radio 1: Trial 1 tiếng (Fast 1-click)
        r1 = tk.Radiobutton(
            plan_frame,
            text="⚡ Dùng thử Trial 1 TIẾNG (Phổ biến cho khách test)",
            variable=self.plan_var,
            value="trial_1h",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#b45309",
            selectcolor="#fef3c7",
            cursor="hand2",
        )
        r1.pack(anchor="w", pady=2)

        # Radio 2: Trial tùy chỉnh số giờ
        trial_custom_frame = tk.Frame(plan_frame, bg="#ffffff")
        trial_custom_frame.pack(anchor="w", pady=2)

        r2 = tk.Radiobutton(
            trial_custom_frame,
            text="🕒 Dùng thử Trial tùy chỉnh:",
            variable=self.plan_var,
            value="trial_custom",
            font=("Segoe UI", 10),
            bg="#ffffff",
            selectcolor="#ffffff",
            cursor="hand2",
        )
        r2.pack(side="left")

        self.hours_var = tk.StringVar(value="2")
        hours_entry = tk.Entry(trial_custom_frame, textvariable=self.hours_var, width=5, font=("Segoe UI", 10), justify="center")
        hours_entry.pack(side="left", padx=4)
        tk.Label(trial_custom_frame, text="tiếng", font=("Segoe UI", 10), bg="#ffffff").pack(side="left")

        # Radio 3: Có thời hạn (Theo ngày)
        days_frame = tk.Frame(plan_frame, bg="#ffffff")
        days_frame.pack(anchor="w", pady=2)

        r3 = tk.Radiobutton(
            days_frame,
            text="📅 Có thời hạn (Subscription):",
            variable=self.plan_var,
            value="days",
            font=("Segoe UI", 10),
            bg="#ffffff",
            selectcolor="#ffffff",
            cursor="hand2",
        )
        r3.pack(side="left")

        self.days_combo = ttk.Combobox(days_frame, values=["30", "60", "90", "180", "365"], width=6, font=("Segoe UI", 10))
        self.days_combo.set("30")
        self.days_combo.pack(side="left", padx=4)
        tk.Label(days_frame, text="ngày", font=("Segoe UI", 10), bg="#ffffff").pack(side="left")

        # Radio 4: Vĩnh viễn (Lifetime)
        r4 = tk.Radiobutton(
            plan_frame,
            text="⭐ Vĩnh viễn (Trọn đời - Lifetime)",
            variable=self.plan_var,
            value="lifetime",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#15803d",
            selectcolor="#dcfce7",
            cursor="hand2",
        )
        r4.pack(anchor="w", pady=2)

        # Generate Button
        self.gen_btn = tk.Button(
            form_card,
            text="✨ TẠO LICENSE KEY NGAY (Enter)",
            font=("Segoe UI", 11, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            pady=8,
            command=self._generate_key,
        )
        self.gen_btn.pack(fill="x", padx=14, pady=(10, 4))
        self.bind("<Return>", lambda _: self._generate_key())

        # 3. Output Card
        output_card = tk.Frame(container, bg="#ffffff", bd=1, relief="solid", highlightthickness=0)
        output_card.config(highlightbackground="#e2e8f0")
        output_card.pack(fill="both", expand=True, ipadx=14, ipady=12)

        tk.Label(
            output_card,
            text="4. Mã bản quyền đã tạo (License Key):",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#1e293b",
        ).pack(anchor="w", padx=14, pady=(0, 4))

        self.key_text = tk.Text(
            output_card,
            height=4,
            font=("Consolas", 10),
            bg="#f8fafc",
            fg="#0f172a",
            relief="solid",
            bd=1,
            wrap="char",
        )
        self.key_text.pack(fill="x", padx=14, pady=(0, 8))

        actions_frame = tk.Frame(output_card, bg="#ffffff")
        actions_frame.pack(fill="x", padx=14, pady=(0, 4))

        self.copy_btn = tk.Button(
            actions_frame,
            text="📋 SAO CHÉP KEY (GỬI KHÁCH)",
            font=("Segoe UI", 10, "bold"),
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            command=self._copy_key,
        )
        self.copy_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        open_folder_btn = tk.Button(
            actions_frame,
            text="📁 Mở thư mục lưu",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            cursor="hand2",
            padx=10,
            command=self._open_licenses_dir,
        )
        open_folder_btn.pack(side="right")

        self.status_lbl = tk.Label(
            output_card,
            text="Nhập mã máy và bấm 'Tạo License Key ngay' để bắt đầu.",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#64748b",
        )
        self.status_lbl.pack(anchor="w", padx=14, pady=(4, 0))

        # Bottom bar
        bottom_bar = tk.Frame(self, bg="#e2e8f0", height=24)
        bottom_bar.pack(fill="x", side="bottom")
        tk.Label(
            bottom_bar,
            text=f"Trạng thái: {self.key_status_text}",
            font=("Segoe UI", 8),
            bg="#e2e8f0",
            fg="#475569",
        ).pack(side="left", padx=12)

    def _paste_clipboard(self):
        try:
            txt = self.clipboard_get().strip()
            self.mid_var.set(txt)
        except Exception:
            pass

    def _on_mid_change(self, *args):
        val = self.mid_var.get().strip().upper()
        if val.startswith("VB-") and len(val) >= 15:
            self.mid_hint.config(text="✓ Mã máy hợp lệ!", fg="#16a34a")
        else:
            self.mid_hint.config(
                text="Định dạng chuẩn: VB-XXXX-XXXX-XXXX-XXXX (Khách lấy từ ứng dụng Voca Basic)",
                fg="#64748b",
            )

    def _generate_key(self):
        if not self.priv_key:
            messagebox.showerror("Lỗi", "Không tìm thấy khóa bí mật (seller_private_key.pem) để ký số.")
            return

        mid = self.mid_var.get().strip().upper()
        if not mid or not mid.startswith("VB-") or len(mid) < 15:
            messagebox.showwarning("Mã máy không hợp lệ", "Vui lòng nhập đúng Mã máy của khách (bắt đầu bằng VB-).")
            self.mid_entry.focus()
            return

        customer = self.cust_var.get().strip() or "Khách Hàng"
        plan = self.plan_var.get()

        lic_type = "lifetime"
        days = None
        hours = None
        is_trial = False

        if plan == "trial_1h":
            lic_type = "time_limited"
            hours = 1.0
            is_trial = True
            desc = "Dùng thử Trial (1 tiếng)"
        elif plan == "trial_custom":
            lic_type = "time_limited"
            is_trial = True
            try:
                hours = float(self.hours_var.get().strip())
                if hours <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("Lỗi", "Số giờ dùng thử không hợp lệ. Vui lòng nhập số dương.")
                return
            desc = f"Dùng thử Trial ({hours:g} tiếng)"
        elif plan == "days":
            lic_type = "time_limited"
            try:
                days = int(self.days_combo.get().strip())
                if days <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("Lỗi", "Số ngày không hợp lệ. Vui lòng nhập số ngày nguyên dương.")
                return
            desc = f"{days} ngày"
        else:
            lic_type = "lifetime"
            desc = "Vĩnh viễn (Trọn đời)"

        try:
            key = generate_key_string(
                self.priv_key,
                machine_id=mid,
                customer_name=customer,
                license_type=lic_type,
                days=days,
                hours=hours,
                is_trial=is_trial,
            )

            # Display key
            self.key_text.delete("1.0", "end")
            self.key_text.insert("end", key)

            # Auto copy
            self.clipboard_clear()
            self.clipboard_append(key)

            # Save receipt file
            out_dir = get_licenses_dir()
            safe_name = "".join(c for c in customer if c.isalnum() or c in (" ", "_", "-")).strip()
            receipt_path = out_dir / f"license_{safe_name}_{int(time.time())}.txt"
            receipt_content = f"""THONG TIN BAN QUYEN VOCA BASIC
======================================================
Khach hang: {customer}
Ma may:     {mid}
Goi cap:    {desc}
Ngay tao:   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

MA KICH HOAT (LICENSE KEY):
{key}
======================================================
"""
            receipt_path.write_text(receipt_content, encoding="utf-8")

            self.status_lbl.config(
                text=f"✓ Đã tạo thành công ({desc}) và tự động chép vào bộ nhớ tạm! Nhấn Ctrl + V để gửi khách.",
                fg="#16a34a",
                font=("Segoe UI", 9, "bold"),
            )
        except Exception as e:
            messagebox.showerror("Lỗi tạo key", f"Đã xảy ra lỗi: {e}")

    def _copy_key(self):
        key = self.key_text.get("1.0", "end").strip()
        if not key:
            messagebox.showinfo("Thông báo", "Chưa có License Key nào được tạo.")
            return
        self.clipboard_clear()
        self.clipboard_append(key)
        self.status_lbl.config(
            text="✓ ĐÃ SAO CHÉP LICENSE KEY! Bạn chỉ cần nhấn Ctrl + V vào Zalo/Telegram để gửi khách.",
            fg="#16a34a",
            font=("Segoe UI", 9, "bold"),
        )

    def _open_licenses_dir(self):
        try:
            d = get_licenses_dir()
            if sys.platform == "win32":
                os.startfile(str(d))
            else:
                subprocess.Popen(["explorer", str(d)])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")


def main():
    app = KeygenApp()
    app.mainloop()


if __name__ == "__main__":
    main()
