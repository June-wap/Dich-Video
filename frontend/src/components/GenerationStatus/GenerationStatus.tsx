import React from 'react';
import { StatusBadge } from '../StatusBadge/StatusBadge';
import { ProgressBar } from '../ProgressBar/ProgressBar';

export type TTSGenerationState = 'IDLE' | 'GENERATING' | 'COMPLETED' | 'ERROR';

export interface GenerationStatusProps {
  state: TTSGenerationState;
  progress?: number; // 0 to 100
  latencyMs?: number;
  errorMessage?: string;
  onCancel?: () => void;
}

export const GenerationStatus: React.FC<GenerationStatusProps> = ({
  state,
  progress = 0,
  latencyMs,
  errorMessage,
  onCancel,
}) => {
  if (state === 'IDLE') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--neutral-50)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <StatusBadge status="neutral" label="IDLE" size="sm" />
          <span style={{ fontSize: '13px', color: 'var(--neutral-600)' }}>
            Sẵn sàng tạo giọng nói (Local inference offline)
          </span>
        </div>
        <span style={{ fontSize: '12px', color: 'var(--neutral-400)' }}>Mock Engine</span>
      </div>
    );
  }

  if (state === 'GENERATING') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px 14px', background: 'var(--color-primary-50)', border: '1px solid var(--color-primary-200)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <StatusBadge status="info" label="GENERATING" size="sm" />
            <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--color-primary-900)' }}>
              Đang tổng hợp âm thanh giọng nói... ({progress}%)
            </span>
          </div>

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              style={{ fontSize: '12px', color: 'var(--color-primary-700)', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Hủy bỏ
            </button>
          )}
        </div>

        <ProgressBar value={progress} size="sm" />
      </div>
    );
  }

  if (state === 'COMPLETED') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <StatusBadge status="success" label="COMPLETED" size="sm" />
          <span style={{ fontSize: '13px', color: 'var(--success-text)', fontWeight: 500 }}>
            Tạo âm thanh thành công
          </span>
        </div>

        {latencyMs && (
          <span style={{ fontSize: '12px', color: 'var(--success-text)', opacity: 0.85 }}>
            Thời gian: {(latencyMs / 1000).toFixed(2)}s
          </span>
        )}
      </div>
    );
  }

  // ERROR
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 'var(--radius-md)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <StatusBadge status="error" label="ERROR" size="sm" />
        <span style={{ fontSize: '13px', color: 'var(--danger-text)', fontWeight: 500 }}>
          {errorMessage || 'Lỗi khi tổng hợp âm thanh. Vui lòng kiểm tra tham số và thử lại.'}
        </span>
      </div>
    </div>
  );
};
