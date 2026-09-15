import React from 'react';
import { Button } from '../Button/Button';

export interface ErrorStateProps {
  title?: string;
  message: string;
  details?: string;
  retryLabel?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Đã xảy ra lỗi',
  message,
  details,
  retryLabel = 'Thử lại',
  onRetry,
  className,
}) => {
  return (
    <div className={`ds-error-state ${className || ''}`}>
      <div className="ds-error-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      </div>

      <div className="ds-error-content">
        <span className="ds-error-title">{title}</span>
        <span className="ds-error-desc">{message}</span>
        {details && (
          <code style={{ fontSize: '11px', marginTop: '4px', background: 'rgba(0,0,0,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
            {details}
          </code>
        )}
      </div>

      {onRetry && (
        <Button size="sm" variant="danger" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
};
