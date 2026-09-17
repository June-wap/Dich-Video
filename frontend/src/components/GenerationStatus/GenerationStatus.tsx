import React from 'react';
import { StatusBadge } from '../StatusBadge/StatusBadge';
import { ProgressBar } from '../ProgressBar/ProgressBar';

export type TTSGenerationState = 'IDLE' | 'QUEUED' | 'GENERATING' | 'COMPLETED' | 'ERROR';

export interface GenerationStatusProps {
  state: TTSGenerationState;
  /** Real progress percentage (0-100), when the caller actually has one.
   * Optional because the persisted Short TTS Job API (Task 2/3) reports no
   * progress field on TTSStatus at all - callers that don't have a real
   * number (Short TTS) omit this and get an honest indeterminate indicator
   * instead of a fabricated percentage. Callers that still simulate progress
   * locally (e.g. LongFormPage) may continue to pass a number unchanged. */
  progress?: number;
  latencyMs?: number;
  errorMessage?: string;
  onCancel?: () => void;
}

export const GenerationStatus: React.FC<GenerationStatusProps> = ({
  state,
  progress,
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
            Sẵn sàng tạo giọng nói
          </span>
        </div>
      </div>
    );
  }

  if (state === 'QUEUED') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px 14px', background: 'var(--neutral-50)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <StatusBadge status="warning" label="QUEUED" size="sm" />
            <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--neutral-700)' }}>
              Đang chờ xử lý trong hàng đợi...
            </span>
          </div>

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              style={{ fontSize: '12px', color: 'var(--neutral-600)', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Ẩn tiến trình
            </button>
          )}
        </div>

        <ProgressBar indeterminate size="sm" />
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
              {typeof progress === 'number'
                ? `Đang tổng hợp âm thanh giọng nói... (${progress}%)`
                : 'Đang tổng hợp âm thanh giọng nói...'}
            </span>
          </div>

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              style={{ fontSize: '12px', color: 'var(--color-primary-700)', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Ẩn tiến trình
            </button>
          )}
        </div>

        {typeof progress === 'number' ? (
          <ProgressBar value={progress} size="sm" />
        ) : (
          <ProgressBar indeterminate size="sm" />
        )}
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
