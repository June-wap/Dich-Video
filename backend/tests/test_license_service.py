import os
import re
import sys
import time
from datetime import datetime, timezone
import pytest

os.environ.setdefault("LOCAL_AI_CHATTERBOX_PYTHON", sys.executable)

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.core.app_paths import resolve_app_paths
from backend.errors import ApplicationError, ErrorCode
from backend.main import create_app
from backend.persistence import Repository
from backend.schemas.license import LicenseStatus, LicenseType
from backend.services.license_service import LicenseService
from scripts.generate_license import generate_license_key, load_or_create_private_key


@pytest.fixture
def test_settings(tmp_path):
    settings = Settings(
        app_name="Voca Basic Test",
        app_version="1.0.0-test",
        app_data_dir=str(tmp_path / "app_data"),
        database_path=str(tmp_path / "data" / "metadata.sqlite3"),
        require_local_token=False,
    )
    return settings


@pytest.fixture
def repo(test_settings):
    return Repository(test_settings)


@pytest.fixture
def priv_key():
    return load_or_create_private_key()


@pytest.fixture
def license_service(test_settings, repo):
    return LicenseService(test_settings, repo)


def test_machine_id_format(license_service):
    mid = license_service.get_machine_id()
    assert mid.startswith("VB-")
    pattern = r"^VB-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$"
    assert re.match(pattern, mid), f"Machine ID {mid} does not match expected format"


def test_unlicensed_by_default(license_service):
    # Ensure fresh state
    license_service.deactivate()
    status = license_service.get_status()
    assert status.status == LicenseStatus.UNLICENSED
    assert status.is_active is False
    with pytest.raises(ApplicationError) as exc_info:
        license_service.verify_license()
    assert exc_info.value.code == ErrorCode.LICENSE_REQUIRED


def test_valid_lifetime_license(license_service, priv_key):
    mid = license_service.get_machine_id()
    key = generate_license_key(
        priv_key,
        machine_id=mid,
        customer_name="Test Customer",
        license_type="lifetime",
    )
    res = license_service.activate(key)
    assert res.is_active is True
    assert res.status == LicenseStatus.ACTIVE
    assert res.customer_name == "Test Customer"
    assert res.license_type == LicenseType.LIFETIME

    # verify_license does not raise
    license_service.verify_license()


def test_valid_time_limited_license(license_service, priv_key):
    mid = license_service.get_machine_id()
    key = generate_license_key(
        priv_key,
        machine_id=mid,
        customer_name="Subscription User",
        license_type="time_limited",
        days=30,
    )
    res = license_service.activate(key)
    assert res.is_active is True
    assert res.status == LicenseStatus.ACTIVE
    assert res.customer_name == "Subscription User"
    assert res.license_type == LicenseType.TIME_LIMITED
    assert res.days_left is not None
    assert 29 <= res.days_left <= 31


def test_expired_license(license_service, priv_key):
    mid = license_service.get_machine_id()
    key = generate_license_key(
        priv_key,
        machine_id=mid,
        customer_name="Expired User",
        license_type="time_limited",
        expires_date_str="2020-01-01",
    )
    with pytest.raises(ApplicationError) as exc_info:
        license_service.activate(key)
    assert exc_info.value.code == ErrorCode.LICENSE_EXPIRED

    status, _, msg = license_service.parse_and_validate_key(key)
    assert status == LicenseStatus.EXPIRED


def test_machine_mismatch(license_service, priv_key):
    other_mid = "VB-9999-8888-7777-6666"
    key = generate_license_key(
        priv_key,
        machine_id=other_mid,
        customer_name="Other Machine User",
        license_type="lifetime",
    )
    with pytest.raises(ApplicationError) as exc_info:
        license_service.activate(key)
    assert exc_info.value.code == ErrorCode.LICENSE_INVALID

    status, _, msg = license_service.parse_and_validate_key(key)
    assert status == LicenseStatus.MACHINE_MISMATCH


def test_tampered_key(license_service, priv_key):
    mid = license_service.get_machine_id()
    key = generate_license_key(priv_key, machine_id=mid, customer_name="Valid")
    # Corrupt key characters
    tampered_key = key[:-4] + "AAAA"
    status, _, _ = license_service.parse_and_validate_key(tampered_key)
    assert status == LicenseStatus.INVALID


def test_clock_rollback_defense(license_service, priv_key, monkeypatch):
    mid = license_service.get_machine_id()
    future_time = time.time() + 100000
    key = generate_license_key(
        priv_key,
        machine_id=mid,
        customer_name="Clock User",
        license_type="time_limited",
        days=30,
    )
    # Simulate run at future time
    license_service._update_last_clock(future_time)

    # Now run at current (earlier) time
    status, _, msg = license_service.parse_and_validate_key(key)
    assert status == LicenseStatus.CLOCK_TAMPERED


def test_api_license_endpoints_and_tts_block(test_settings):
    app = create_app(test_settings)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        # 1. License status when fresh
        resp = client.get("/api/license/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("UNLICENSED", "ACTIVE")
        mid = data["machine_id"]
        assert mid.startswith("VB-")

        # Deactivate to ensure unlicensed for TTS block test
        client.post("/api/license/deactivate")

        # 2. TTS request should be rejected with 403 LICENSE_REQUIRED
        tts_payload = {
            "text": "Xin chào thế giới",
            "voice_id": "default",
            "speed": 1.0,
        }
        tts_resp = client.post("/api/tts", json=tts_payload)
        assert tts_resp.status_code == 403
        assert tts_resp.json()["error"]["code"] == "LICENSE_REQUIRED"

        # 3. Activate via API
        priv = load_or_create_private_key()
        valid_key = generate_license_key(priv, machine_id=mid, customer_name="API User", license_type="lifetime")
        act_resp = client.post("/api/license/activate", json={"license_key": valid_key})
        assert act_resp.status_code == 200
        assert act_resp.json()["ok"] is True
        assert act_resp.json()["status"]["is_active"] is True
        assert act_resp.json()["status"]["customer_name"] == "API User"

        # Check status again
        status_resp = client.get("/api/license/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["is_active"] is True
        assert status_resp.json()["status"] == "ACTIVE"


def _make_v2_token(priv_key, machine_id: str, plan: str = "lifetime", exp=None, val=None, cust: str = "Cloud User") -> str:
    import base64
    import hashlib
    import json
    mid_hash = hashlib.sha256(machine_id.strip().upper().encode("utf-8")).hexdigest()
    now_sec = int(time.time())
    payload = {
        "v": 2,
        "p": "voca-basic",
        "lid": "test-license-hash-64charslong1234567890abcdef1234567890abcdef1234",
        "mid": mid_hash,
        "plan": plan,
        "iat": now_sec,
        "exp": exp,
        "val": val if val is not None else (now_sec + 30 * 86400),
        "cust": cust,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = priv_key.sign(payload_bytes)
    p_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    s_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{p_b64}.{s_b64}"


def test_v2_valid_lifetime_token(license_service, priv_key):
    mid = license_service.get_machine_id()
    token = _make_v2_token(priv_key, machine_id=mid, plan="lifetime", cust="Alice")
    license_service._save_key(token)

    status = license_service.get_status()
    assert status.status == LicenseStatus.ACTIVE
    assert status.is_active is True
    assert status.customer_name == "Alice"
    assert status.license_type == LicenseType.LIFETIME
    assert status.is_cloud_managed is True
    assert status.validation_until is not None

    license_service.verify_license()


def test_v2_valid_time_limited_token(license_service, priv_key):
    mid = license_service.get_machine_id()
    exp_time = int(time.time() + 15 * 86400)
    token = _make_v2_token(priv_key, machine_id=mid, plan="time_limited", exp=exp_time, cust="Bob")
    license_service._save_key(token)

    status = license_service.get_status()
    assert status.status == LicenseStatus.ACTIVE
    assert status.is_active is True
    assert status.customer_name == "Bob"
    assert status.license_type == LicenseType.TIME_LIMITED
    assert status.days_left is not None
    assert 14 <= status.days_left <= 16


def test_v2_tampered_token(license_service, priv_key):
    mid = license_service.get_machine_id()
    token = _make_v2_token(priv_key, machine_id=mid)
    parts = token.split(".")
    tampered_sig = parts[1][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{tampered_sig}"

    st, _, _ = license_service.parse_and_validate_key(tampered_token)
    assert st == LicenseStatus.INVALID


def test_v2_machine_mismatch(license_service, priv_key):
    token = _make_v2_token(priv_key, machine_id="VB-9999-9999-9999-9999")
    st, _, msg = license_service.parse_and_validate_key(token)
    assert st == LicenseStatus.MACHINE_MISMATCH


def test_v2_lease_grace_period(license_service, priv_key):
    mid = license_service.get_machine_id()
    # Expired lease by 2 days, but within 7 days grace period
    val_time = int(time.time() - 2 * 86400)
    token = _make_v2_token(priv_key, machine_id=mid, val=val_time)
    license_service._save_key(token)

    status = license_service.get_status()
    assert status.status == LicenseStatus.ACTIVE
    assert status.grace_period_active is True
    assert "ân hạn" in status.message


def test_v2_lease_expired(license_service, priv_key):
    mid = license_service.get_machine_id()
    # Expired lease by 10 days (> 7 days grace period)
    val_time = int(time.time() - 10 * 86400)
    token = _make_v2_token(priv_key, machine_id=mid, val=val_time)
    license_service._save_key(token)

    status = license_service.get_status()
    assert status.status == LicenseStatus.LEASE_EXPIRED
    assert status.is_active is False

    with pytest.raises(ApplicationError) as exc_info:
        license_service.verify_license()
    assert exc_info.value.code == ErrorCode.LEASE_EXPIRED


def test_v2_clock_rollback(license_service, priv_key):
    mid = license_service.get_machine_id()
    exp_time = int(time.time() + 15 * 86400)
    token = _make_v2_token(priv_key, machine_id=mid, plan="time_limited", exp=exp_time)

    # Set last clock far into the future
    future = time.time() + 86400
    license_service._update_last_clock(future)

    st, _, msg = license_service.parse_and_validate_key(token)
    assert st == LicenseStatus.CLOCK_TAMPERED


def test_v2_online_activation_success_mock(license_service, priv_key, monkeypatch):
    mid = license_service.get_machine_id()
    v2_key = "VB-ABCD-EFGH-1234-5678-9999"
    mock_token = _make_v2_token(priv_key, machine_id=mid, cust="Online User")

    def mock_post(url, payload, timeout_seconds=10.0):
        return 200, {
            "ok": True,
            "status": "active",
            "activationToken": mock_token,
            "plan": "lifetime",
            "validationUntil": "2026-10-21T00:00:00Z"
        }

    # Inject mock cloud URL & HTTP post
    license_service._settings = Settings(
        app_name="Test",
        cloud_license_url="https://mock-cloud.functions.net"
    )
    monkeypatch.setattr(license_service, "_http_post_json", mock_post)

    res = license_service.activate(v2_key)
    assert res.is_active is True
    assert res.customer_name == "Online User"
    assert res.is_cloud_managed is True


def test_v2_online_activation_device_limit_mock(license_service, monkeypatch):
    v2_key = "VB-ABCD-EFGH-1234-5678-9999"

    def mock_post(url, payload, timeout_seconds=10.0):
        return 409, {
            "ok": False,
            "errorCode": "DEVICE_LIMIT_REACHED",
            "message": "Đã đạt giới hạn thiết bị"
        }

    license_service._settings = Settings(
        app_name="Test",
        cloud_license_url="https://mock-cloud.functions.net"
    )
    monkeypatch.setattr(license_service, "_http_post_json", mock_post)

    with pytest.raises(ApplicationError) as exc_info:
        license_service.activate(v2_key)
    assert exc_info.value.code == ErrorCode.DEVICE_LIMIT_REACHED


def test_v2_online_activation_blocked_mock(license_service, monkeypatch):
    v2_key = "VB-ABCD-EFGH-1234-5678-9999"

    def mock_post(url, payload, timeout_seconds=10.0):
        return 400, {
            "ok": False,
            "errorCode": "LICENSE_BLOCKED",
            "message": "Bản quyền bị khóa"
        }

    license_service._settings = Settings(
        app_name="Test",
        cloud_license_url="https://mock-cloud.functions.net"
    )
    monkeypatch.setattr(license_service, "_http_post_json", mock_post)

    with pytest.raises(ApplicationError) as exc_info:
        license_service.activate(v2_key)
    assert exc_info.value.code == ErrorCode.LICENSE_BLOCKED


