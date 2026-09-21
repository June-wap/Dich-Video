"""Hardware-bound cryptographic offline licensing & Cloud License V2 for Voca Basic.

Supports:
1. License V1: Offline Ed25519 asymmetric signature directly tied to hardware Machine ID.
2. License V2: Cloud-assisted activation (Firebase Cloud Functions / Firestore) with
   Ed25519-signed offline activation tokens, lease renewal, and device limits.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.config import Settings
from backend.core.app_paths import resolve_app_paths
from backend.errors import ApplicationError, ErrorCode
from backend.persistence import Repository
from backend.schemas.license import (
    LicenseStatus,
    LicenseStatusResponse,
    LicenseType,
)

logger = logging.getLogger("backend.license")

# Embedded Master Public Key for Offline License V1 (Hex, 32 bytes)
# Generated from scripts/seller_private_key.pem
V1_PUBLIC_KEY_HEX = "4a27f04823be5ac5e40341d5a549c78fef9dfafad3e29fc466ef89db5cc40f1c"

# Setting keys in SQLite metadata table
SETTING_KEY_LICENSE = "license_key"
SETTING_KEY_LAST_CLOCK = "license_last_clock"

V2_KEY_PATTERN = re.compile(r"^VB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def _b64decode_padded(s: str) -> bytes:
    """Safely decode base64 / base64url string with missing padding."""
    clean = s.strip().replace("-", "+").replace("_", "/")
    missing_padding = len(clean) % 4
    if missing_padding:
        clean += "=" * (4 - missing_padding)
    return base64.b64decode(clean)


def _b64encode_clean(data: bytes) -> str:
    """Encode bytes to URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


class LicenseService:
    def __init__(self, settings: Settings, persistence: Repository | None = None) -> None:
        self._settings = settings
        self._app_paths = resolve_app_paths()
        self._persistence = persistence or Repository(settings)
        self._cached_machine_id: Optional[str] = None
        self._license_file = self._app_paths.settings_dir / "license.key"

        # Initialize V1 public key
        try:
            self._v1_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(V1_PUBLIC_KEY_HEX)
            )
        except Exception as exc:
            logger.error("license_v1_public_key_init_failed error=%s", exc)
            raise RuntimeError(f"Invalid V1 license public key: {exc}") from exc

        # Initialize V2 Cloud public key (if configured; otherwise falls back to V1 key)
        v2_hex = settings.cloud_license_public_key_hex or V1_PUBLIC_KEY_HEX
        try:
            self._v2_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(v2_hex)
            )
        except Exception as exc:
            logger.warning("license_v2_public_key_init_warning error=%s, using v1 key", exc)
            self._v2_public_key = self._v1_public_key

    def get_machine_id(self) -> str:
        """Returns stable hardware-bound Machine ID formatted as VB-XXXX-XXXX-XXXX-XXXX."""
        if self._cached_machine_id:
            return self._cached_machine_id

        machine_guid = ""
        system_uuid = ""

        # 1. Windows Registry MachineGuid (always present on Windows, fast & stable)
        if platform.system() == "Windows":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    val, _ = winreg.QueryValueEx(key, "MachineGuid")
                    if val and isinstance(val, str):
                        machine_guid = val.strip()
            except Exception as exc:
                logger.debug("winreg_machine_guid_query_failed: %s", exc)

        # 2. Motherboard UUID via PowerShell CIM (tied to hardware/BIOS)
        if platform.system() == "Windows":
            try:
                cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                if res.returncode == 0 and res.stdout:
                    out = res.stdout.strip()
                    if out and "error" not in out.lower() and len(out) > 8:
                        system_uuid = out
            except Exception as exc:
                logger.debug("powershell_uuid_query_failed: %s", exc)

        # Combine hardware sources, fallback if needed
        raw_source = f"{system_uuid}:{machine_guid}"
        if not system_uuid and not machine_guid:
            raw_source = f"FALLBACK:{platform.node()}:{os.environ.get('USERNAME', 'USER')}"

        digest = hashlib.sha256(raw_source.encode("utf-8")).hexdigest().upper()
        self._cached_machine_id = f"VB-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"
        return self._cached_machine_id

    def _get_stored_key(self) -> Optional[str]:
        """Retrieve license key/token from DB or fallback to file on disk."""
        try:
            val = self._persistence.get_setting(SETTING_KEY_LICENSE)
            if val and isinstance(val, str) and len(val.strip()) > 10:
                return val.strip()
        except Exception:
            pass

        if self._license_file.is_file():
            try:
                content = self._license_file.read_text(encoding="utf-8").strip()
                if content and len(content) > 10:
                    self._persistence.put("settings", SETTING_KEY_LICENSE, content)
                    return content
            except Exception as exc:
                logger.warning("failed_to_read_license_file path=%s error=%s", self._license_file, exc)

        return None

    def _save_key(self, key_str: str) -> None:
        """Store license key/token in DB and disk file."""
        clean_key = key_str.strip()
        self._persistence.put("settings", SETTING_KEY_LICENSE, clean_key)
        try:
            self._license_file.parent.mkdir(parents=True, exist_ok=True)
            self._license_file.write_text(clean_key, encoding="utf-8")
        except Exception as exc:
            logger.warning("failed_to_write_license_file error=%s", exc)

    def _clear_key(self) -> None:
        """Remove license key/token from DB and disk."""
        try:
            with self._persistence.connect() as db:
                db.execute("DELETE FROM settings WHERE key=?", (SETTING_KEY_LICENSE,))
        except Exception:
            pass
        if self._license_file.is_file():
            try:
                self._license_file.unlink(missing_ok=True)
            except Exception:
                pass

    def _get_last_clock(self) -> Optional[float]:
        try:
            val = self._persistence.get_setting(SETTING_KEY_LAST_CLOCK)
            if val is not None:
                return float(val)
        except Exception:
            pass
        return None

    def _update_last_clock(self, ts: float) -> None:
        try:
            self._persistence.put("settings", SETTING_KEY_LAST_CLOCK, ts)
        except Exception:
            pass

    def _http_post_json(self, url: str, payload: dict, timeout_seconds: float = 10.0) -> Tuple[int, dict]:
        """Safe HTTPS POST helper using standard library urllib."""
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"VocaBasic/{self._settings.app_version} (Windows)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                status_code = response.getcode()
                body = response.read().decode("utf-8")
                return status_code, json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                return exc.code, json.loads(body)
            except Exception:
                return exc.code, {"ok": False, "message": str(exc)}
        except Exception as exc:
            logger.warning("http_post_failed url=%s error=%s", url, exc)
            return 503, {"ok": false, "errorCode": "SERVICE_UNAVAILABLE", "message": "Không thể kết nối đến máy chủ bản quyền."}

    def parse_and_validate_key(self, raw_key: str) -> Tuple[LicenseStatus, Optional[Dict[str, Any]], str]:
        """Validates key/token syntax, signature, machine match, and expiry.

        Supports both V1 offline keys and V2 signed activation tokens.
        """
        if not raw_key or not raw_key.strip():
            return LicenseStatus.UNLICENSED, None, "Chưa có mã kích hoạt bản quyền."

        text = raw_key.strip()
        if "-----BEGIN" in text:
            lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("-----")]
            text = "".join(lines)

        parts = text.split(".")
        if len(parts) != 2:
            return LicenseStatus.INVALID, None, "Định dạng mã kích hoạt không hợp lệ."

        payload_b64, sig_b64 = parts[0], parts[1]

        try:
            payload_bytes = _b64decode_padded(payload_b64)
            sig_bytes = _b64decode_padded(sig_b64)
        except Exception:
            return LicenseStatus.INVALID, None, "Mã kích hoạt bị hỏng hoặc chứa ký tự không hợp lệ."

        if len(sig_bytes) != 64:
            return LicenseStatus.INVALID, None, "Chữ ký số bản quyền không đúng tiêu chuẩn (Ed25519)."

        # Parse JSON payload
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return LicenseStatus.INVALID, None, "Dữ liệu bản quyền không thể giải mã JSON."

        version = payload.get("v", 1)
        now = time.time()

        # ====================================================
        # CASE 1: CLOUD LICENSE V2 SIGNED TOKEN
        # ====================================================
        if version == 2 and payload.get("p") == "voca-basic":
            # Verify with V2 Cloud public key (or V1 key if identical)
            verified = False
            for pub in (self._v2_public_key, self._v1_public_key):
                try:
                    pub.verify(sig_bytes, payload_bytes)
                    verified = True
                    break
                except InvalidSignature:
                    continue
                except Exception:
                    pass

            if not verified:
                return LicenseStatus.INVALID, None, "Chữ ký số token bản quyền không hợp lệ hoặc đã bị chỉnh sửa."

            # Verify Machine ID Hash
            target_mid_hash = payload.get("mid")
            current_mid = self.get_machine_id()
            expected_mid_hash = hashlib.sha256(current_mid.upper().encode("utf-8")).hexdigest()

            if not target_mid_hash or target_mid_hash.lower() != expected_mid_hash.lower():
                return (
                    LicenseStatus.MACHINE_MISMATCH,
                    payload,
                    f"Token bản quyền này không dành cho máy tính này (Máy: {current_mid})."
                )

            # Expiration check for time-limited licenses
            lic_plan = payload.get("plan", "lifetime")
            exp = payload.get("exp")
            if lic_plan == "time_limited" and exp is not None:
                exp_ts = float(exp)
                # Anti-tampering Clock Rollback Check
                last_clock = self._get_last_clock()
                if last_clock is not None and now < (last_clock - 3600):
                    logger.warning("clock_rollback_detected now=%s last_clock=%s", now, last_clock)
                    return (
                        LicenseStatus.CLOCK_TAMPERED,
                        payload,
                        "Phát hiện thời gian hệ thống bị lùi ngược. Vui lòng chỉnh lại đúng giờ máy tính."
                    )
                self._update_last_clock(max(last_clock or 0.0, now))

                if now > exp_ts:
                    dt_str = datetime.fromtimestamp(exp_ts, tz=timezone.utc).strftime("%d/%m/%Y")
                    return (
                        LicenseStatus.EXPIRED,
                        payload,
                        f"Bản quyền đã hết hạn vào ngày {dt_str}. Vui lòng gia hạn để tiếp tục sử dụng."
                    )

            # Validation lease check (Offline lease duration)
            val = payload.get("val")
            grace_seconds = (self._settings.offline_lease_grace_days or 7) * 86400
            if val is not None:
                val_ts = float(val)
                if now > (val_ts + grace_seconds):
                    return (
                        LicenseStatus.LEASE_EXPIRED,
                        payload,
                        "Đã hết thời hạn sử dụng ngoại tuyến. Vui lòng kết nối Internet để đồng bộ bản quyền."
                    )
                elif now > val_ts:
                    payload["_grace_active"] = True

            payload["_is_cloud_managed"] = True
            return LicenseStatus.ACTIVE, payload, "Bản quyền Cloud hợp lệ và đang hoạt động."

        # ====================================================
        # CASE 2: LEGACY OFFLINE LICENSE V1
        # ====================================================
        try:
            self._v1_public_key.verify(sig_bytes, payload_bytes)
        except InvalidSignature:
            return LicenseStatus.INVALID, None, "Chữ ký số không khớp hoặc mã bản quyền đã bị chỉnh sửa."
        except Exception as exc:
            return LicenseStatus.INVALID, None, f"Lỗi xác thực chữ ký bản quyền: {exc}"

        target_machine = payload.get("m") or payload.get("machine_id")
        current_machine = self.get_machine_id()
        if not target_machine or target_machine.strip().upper() != current_machine.upper():
            return (
                LicenseStatus.MACHINE_MISMATCH,
                payload,
                f"Mã bản quyền này không dành cho máy tính này (Máy: {current_machine}, Key: {target_machine})."
            )

        lic_type = payload.get("t") or payload.get("type", "lifetime")
        if lic_type == "time_limited":
            expires_val = payload.get("e") or payload.get("expires_at")
            if not expires_val:
                return LicenseStatus.INVALID, payload, "Mã bản quyền có thời hạn thiếu thông tin ngày hết hạn."

            if isinstance(expires_val, (int, float)):
                expires_ts = float(expires_val)
            else:
                try:
                    dt = datetime.fromisoformat(str(expires_val).replace("Z", "+00:00"))
                    expires_ts = dt.timestamp()
                except Exception:
                    return LicenseStatus.INVALID, payload, "Định dạng ngày hết hạn không hợp lệ."

            last_clock = self._get_last_clock()
            if last_clock is not None and now < (last_clock - 3600):
                logger.warning("clock_rollback_detected now=%s last_clock=%s", now, last_clock)
                return (
                    LicenseStatus.CLOCK_TAMPERED,
                    payload,
                    "Phát hiện thời gian hệ thống bị lùi ngược so với lịch sử sử dụng. Vui lòng chỉnh lại đúng giờ máy tính."
                )

            self._update_last_clock(max(last_clock or 0.0, now))

            if now > expires_ts:
                dt_str = datetime.fromtimestamp(expires_ts, tz=timezone.utc).strftime("%d/%m/%Y")
                return (
                    LicenseStatus.EXPIRED,
                    payload,
                    f"Bản quyền đã hết hạn vào ngày {dt_str}. Vui lòng liên hệ người bán để gia hạn."
                )

        payload["_is_cloud_managed"] = False
        return LicenseStatus.ACTIVE, payload, "Bản quyền offline hợp lệ và đang hoạt động."

    def get_status(self) -> LicenseStatusResponse:
        """Returns full status of the current installation."""
        machine_id = self.get_machine_id()
        raw_key = self._get_stored_key()

        if not raw_key:
            return LicenseStatusResponse(
                status=LicenseStatus.UNLICENSED,
                is_active=False,
                machine_id=machine_id,
                message="Phần mềm chưa được kích hoạt bản quyền. Vui lòng cung cấp Mã máy để nhận License Key."
            )

        status, payload, message = self.parse_and_validate_key(raw_key)

        customer_name = payload.get("cust") or payload.get("c") or payload.get("customer_name") if payload else None
        raw_type = payload.get("plan") or payload.get("t") or payload.get("type", "lifetime") if payload else None
        lic_type = LicenseType.TIME_LIMITED if raw_type == "time_limited" else (LicenseType.LIFETIME if raw_type else None)
        issued_at = payload.get("i") or payload.get("issued_at") if payload else None

        expires_at_str: Optional[str] = None
        days_left: Optional[int] = None
        time_left_str: Optional[str] = None
        is_trial = bool(payload.get("trial", False)) if payload else False
        is_cloud_managed = bool(payload.get("_is_cloud_managed", False)) if payload else False
        grace_period_active = bool(payload.get("_grace_active", False)) if payload else False

        validation_until_str: Optional[str] = None
        if payload and payload.get("val"):
            val_dt = datetime.fromtimestamp(float(payload["val"]), tz=timezone.utc)
            validation_until_str = val_dt.astimezone().strftime("%d/%m/%Y %H:%M")

        if payload and lic_type == LicenseType.TIME_LIMITED:
            expires_val = payload.get("exp") or payload.get("e") or payload.get("expires_at")
            if expires_val:
                if isinstance(expires_val, (int, float)):
                    dt = datetime.fromtimestamp(float(expires_val), tz=timezone.utc)
                else:
                    dt = datetime.fromisoformat(str(expires_val).replace("Z", "+00:00"))
                seconds_left = dt.timestamp() - time.time()
                local_dt = dt.astimezone()
                if seconds_left < 172800:
                    expires_at_str = local_dt.strftime("%H:%M ngày %d/%m/%Y")
                else:
                    expires_at_str = local_dt.strftime("%d/%m/%Y")

                if seconds_left <= 0:
                    days_left = 0
                    time_left_str = "Đã hết hạn"
                elif seconds_left < 3600:
                    mins = max(1, int(seconds_left // 60))
                    days_left = 0
                    time_left_str = f"{mins} phút"
                elif seconds_left < 86400:
                    hrs = max(1, int(seconds_left // 3600))
                    days_left = 0
                    time_left_str = f"{hrs} giờ"
                else:
                    days = int(seconds_left // 86400) + 1
                    days_left = days
                    time_left_str = f"{days} ngày"

        if is_trial and status == LicenseStatus.ACTIVE:
            message = f"Bản quyền dùng thử (Còn {time_left_str})."
        elif grace_period_active and status == LicenseStatus.ACTIVE:
            message = f"Bản quyền đang trong thời gian ân hạn ngoại tuyến. Vui lòng kết nối Internet sớm để đồng bộ."

        is_active = (status == LicenseStatus.ACTIVE)

        return LicenseStatusResponse(
            status=status,
            is_active=is_active,
            machine_id=machine_id,
            customer_name=customer_name,
            license_type=lic_type,
            issued_at=issued_at,
            expires_at=expires_at_str,
            days_left=days_left,
            time_left_str=time_left_str,
            is_trial=is_trial,
            message=message,
            is_cloud_managed=is_cloud_managed,
            validation_until=validation_until_str,
            grace_period_active=grace_period_active,
        )

    def activate(self, license_key: str) -> LicenseStatusResponse:
        """Attempts to activate software with provided key (V2 Cloud or V1 Offline)."""
        clean_key = license_key.strip()
        machine_id = self.get_machine_id()

        # Check if this is a Cloud License Key V2 (e.g. VB-XXXX-XXXX-XXXX-XXXX-XXXX)
        is_cloud_key = bool(V2_KEY_PATTERN.match(clean_key.upper()))

        if is_cloud_key:
            cloud_url = self._settings.cloud_license_url
            if not cloud_url:
                raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)

            endpoint = f"{cloud_url.rstrip('/')}/activateLicenseEndpoint"
            status_code, resp_json = self._http_post_json(
                endpoint,
                {
                    "licenseKey": clean_key,
                    "machineId": machine_id,
                    "appVersion": self._settings.app_version,
                },
                timeout_seconds=12.0
            )

            if not resp_json.get("ok"):
                error_code = resp_json.get("errorCode", "LICENSE_INVALID")
                if error_code == "DEVICE_LIMIT_REACHED":
                    raise ApplicationError(ErrorCode.DEVICE_LIMIT_REACHED)
                elif error_code == "LICENSE_BLOCKED":
                    raise ApplicationError(ErrorCode.LICENSE_BLOCKED)
                elif error_code == "LICENSE_EXPIRED":
                    raise ApplicationError(ErrorCode.LICENSE_EXPIRED)
                else:
                    raise ApplicationError(ErrorCode.LICENSE_INVALID)

            activation_token = resp_json.get("activationToken")
            if not activation_token:
                raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)

            # Validate signed token locally
            status, _, _ = self.parse_and_validate_key(activation_token)
            if status != LicenseStatus.ACTIVE:
                raise ApplicationError(ErrorCode.TOKEN_INVALID)

            self._save_key(activation_token)
            logger.info("cloud_license_activated_successfully machine_id=%s", machine_id)
            return self.get_status()

        # Offline License V1 Path
        status, payload, message = self.parse_and_validate_key(clean_key)
        if status != LicenseStatus.ACTIVE:
            if status == LicenseStatus.EXPIRED:
                raise ApplicationError(ErrorCode.LICENSE_EXPIRED)
            elif status == LicenseStatus.CLOCK_TAMPERED:
                raise ApplicationError(ErrorCode.LICENSE_CLOCK_TAMPERED)
            else:
                raise ApplicationError(ErrorCode.LICENSE_INVALID)

        self._save_key(clean_key)
        logger.info("offline_license_activated_successfully machine_id=%s", machine_id)
        return self.get_status()

    def refresh_license(self) -> LicenseStatusResponse:
        """Attempts to synchronize & refresh license token with Cloud."""
        raw_key = self._get_stored_key()
        if not raw_key:
            return self.get_status()

        status, payload, _ = self.parse_and_validate_key(raw_key)
        if not payload or not payload.get("_is_cloud_managed"):
            # Not a cloud license, nothing to refresh
            return self.get_status()

        cloud_url = self._settings.cloud_license_url
        if not cloud_url:
            return self.get_status()

        endpoint = f"{cloud_url.rstrip('/')}/validateLicenseEndpoint"
        status_code, resp_json = self._http_post_json(
            endpoint,
            {
                "activationToken": raw_key,
                "machineId": self.get_machine_id(),
            },
            timeout_seconds=8.0
        )

        if resp_json.get("ok") and resp_json.get("activationToken"):
            new_token = resp_json["activationToken"]
            val_status, _, _ = self.parse_and_validate_key(new_token)
            if val_status == LicenseStatus.ACTIVE:
                self._save_key(new_token)
                logger.info("license_token_refreshed_from_cloud")
        elif resp_json.get("errorCode") == "ACTIVATION_REVOKED":
            logger.warning("license_activation_revoked_by_cloud")
            self._clear_key()
        elif resp_json.get("errorCode") == "LICENSE_BLOCKED":
            logger.warning("license_blocked_by_cloud")
            # Could keep token to show blocked status

        return self.get_status()

    def deactivate(self) -> None:
        """Deactivate and remove license locally, notifying Cloud if applicable."""
        raw_key = self._get_stored_key()
        if raw_key:
            status, payload, _ = self.parse_and_validate_key(raw_key)
            if payload and payload.get("_is_cloud_managed") and self._settings.cloud_license_url:
                endpoint = f"{self._settings.cloud_license_url.rstrip('/')}/deactivateLicenseEndpoint"
                try:
                    self._http_post_json(
                        endpoint,
                        {
                            "activationToken": raw_key,
                            "machineId": self.get_machine_id(),
                        },
                        timeout_seconds=5.0
                    )
                except Exception as exc:
                    logger.warning("cloud_deactivation_call_failed error=%s", exc)

        self._clear_key()
        logger.info("license_deactivated machine_id=%s", self.get_machine_id())

    def verify_license(self) -> None:
        """Raises ApplicationError if license is not active. Fast in-memory check."""
        resp = self.get_status()
        if not resp.is_active:
            if resp.status == LicenseStatus.EXPIRED:
                raise ApplicationError(ErrorCode.LICENSE_EXPIRED)
            elif resp.status == LicenseStatus.CLOCK_TAMPERED:
                raise ApplicationError(ErrorCode.LICENSE_CLOCK_TAMPERED)
            elif resp.status == LicenseStatus.BLOCKED:
                raise ApplicationError(ErrorCode.LICENSE_BLOCKED)
            elif resp.status == LicenseStatus.DEVICE_LIMIT_REACHED:
                raise ApplicationError(ErrorCode.DEVICE_LIMIT_REACHED)
            elif resp.status == LicenseStatus.REVOKED:
                raise ApplicationError(ErrorCode.ACTIVATION_REVOKED)
            elif resp.status == LicenseStatus.LEASE_EXPIRED:
                raise ApplicationError(ErrorCode.LEASE_EXPIRED)
            elif resp.status in (LicenseStatus.INVALID, LicenseStatus.MACHINE_MISMATCH):
                raise ApplicationError(ErrorCode.LICENSE_INVALID)
            else:
                raise ApplicationError(ErrorCode.LICENSE_REQUIRED)
