import React, { useState } from 'react';
import { Modal } from '../Modal/Modal';
import { Button } from '../Button/Button';
import { TextArea } from '../TextArea/TextArea';
import { licenseService, type LicenseStatusResponse } from '../../services/licenseService';
import { ApiError } from '../../services/httpClient';

export interface LicenseActivationModalProps {
  isOpen: boolean;
  onClose: () => void;
  statusData: LicenseStatusResponse | null;
  onActivated: (status: LicenseStatusResponse) => void;
}

export const LicenseActivationModal: React.FC<LicenseActivationModalProps> = ({
  isOpen,
  onClose,
  statusData,
  onActivated,
}) => {
  const [keyInput, setKeyInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const machineId = statusData?.machine_id || 'Đang lấy...';

  const handleCopyMachineId = () => {
    if (!statusData?.machine_id) return;
    navigator.clipboard.writeText(statusData.machine_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  const handleActivate = async () => {
    if (!keyInput.trim()) {
      setErrorMsg('Vui lòng dán mã bản quyền vào ô bên dưới.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await licenseService.activate(keyInput.trim());
      if (res.ok) {
        setSuccessMsg('Kích hoạt bản quyền thành công!');
        onActivated(res.status);
        setTimeout(() => {
          setSuccessMsg(null);
          setKeyInput('');
          onClose();
        }, 1200);
      } else {
        setErrorMsg(res.status.message || 'Kích hoạt thất bại. Vui lòng kiểm tra lại mã.');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('Không thể kết nối dịch vụ Voca Basic cục bộ. Vui lòng đóng và mở lại ứng dụng.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Kích hoạt bản quyền Voca Basic"
      description="Hỗ trợ kích hoạt trực tuyến qua Cloud License V2 (VB-XXXX-...) hoặc mã offline V1."
      size="lg"
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', width: '100%' }}>
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            Đóng
          </Button>
          <Button
            variant="primary"
            onClick={handleActivate}
            isLoading={loading}
            disabled={loading || !keyInput.trim()}
          >
            Kích hoạt ngay
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Machine ID Box */}
        <div
          style={{
            background: 'var(--neutral-50, #f8fafc)',
            border: '1px solid var(--neutral-200, #e2e8f0)',
            borderRadius: '8px',
            padding: '12px 16px',
          }}
        >
          <div
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--neutral-600, #475569)',
              textTransform: 'uppercase',
              marginBottom: '6px',
            }}
          >
            Mã máy của bạn (Machine ID)
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
            }}
          >
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: '18px',
                fontWeight: 700,
                color: 'var(--primary-700, #1d4ed8)',
                letterSpacing: '1px',
              }}
            >
              {machineId}
            </span>
            <Button
              variant={copied ? 'secondary' : 'outline'}
              size="sm"
              onClick={handleCopyMachineId}
              type="button"
            >
              {copied ? '✓ Đã sao chép' : 'Sao chép mã máy'}
            </Button>
          </div>
          <div
            style={{
              fontSize: '12px',
              color: 'var(--neutral-500, #64748b)',
              marginTop: '6px',
              lineHeight: '1.4',
            }}
          >
            👉 Hãy sao chép <b>Mã máy</b> này và gửi cho người bán qua Zalo/Telegram để nhận mã kích hoạt.
          </div>
        </div>

        {/* Current status if any */}
        {statusData && (
          <div style={{ fontSize: '13px', color: 'var(--neutral-600, #475569)' }}>
            Trạng thái hiện tại:{' '}
            <strong
              style={{
                color: statusData.is_active
                  ? 'var(--success-600, #16a34a)'
                  : 'var(--danger-600, #dc2626)',
              }}
            >
              {statusData.message}
            </strong>
          </div>
        )}

        {/* Input for License Key */}
        <div>
          <label
            htmlFor="license-key-input"
            style={{
              display: 'block',
              fontSize: '13px',
              fontWeight: 600,
              marginBottom: '6px',
              color: 'var(--neutral-700, #334155)',
            }}
          >
            Mã kích hoạt bản quyền (License Key)
          </label>
          <TextArea
            id="license-key-input"
            rows={4}
            placeholder="Dán mã kích hoạt bản quyền do người bán cung cấp vào đây..."
            value={keyInput}
            onChange={(e) => {
              setKeyInput(e.target.value);
              setErrorMsg(null);
            }}
            disabled={loading}
            style={{ fontFamily: 'monospace', fontSize: '12px' }}
          />
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div
            style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#991b1b',
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '13px',
            }}
          >
            ⚠️ {errorMsg}
          </div>
        )}

        {/* Success Alert */}
        {successMsg && (
          <div
            style={{
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              color: '#166534',
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '13px',
            }}
          >
            🎉 {successMsg}
          </div>
        )}
      </div>
    </Modal>
  );
};
