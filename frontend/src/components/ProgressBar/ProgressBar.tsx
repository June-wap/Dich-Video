import React from 'react';
import type { ComponentSize } from '../../types';
import { cn, clamp } from '../../utils';

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
  max?: number;
  label?: string;
  showPercent?: boolean;
  status?: 'default' | 'success' | 'warning' | 'error';
  size?: ComponentSize;
  indeterminate?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value = 0,
  max = 100,
  label,
  showPercent = false,
  status = 'default',
  size = 'md',
  indeterminate = false,
  className,
  ...props
}) => {
  const percentage = indeterminate ? 0 : clamp(Math.round((value / max) * 100), 0, 100);

  return (
    <div className={cn('ds-progress-container', className)} {...props}>
      {(label || showPercent) && (
        <div className="ds-progress-header">
          {label && <span className="ds-progress-label">{label}</span>}
          {showPercent && !indeterminate && (
            <span className="ds-progress-percent">{percentage}%</span>
          )}
          {indeterminate && <span className="ds-progress-percent">Processing...</span>}
        </div>
      )}
      <div
        className={cn('ds-progress-track', `ds-progress-track--${size}`)}
        role="progressbar"
        aria-valuenow={indeterminate ? undefined : percentage}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            'ds-progress-fill',
            status !== 'default' && `ds-progress-fill--${status}`,
            indeterminate && 'ds-progress-fill--indeterminate'
          )}
          style={{ width: indeterminate ? undefined : `${percentage}%` }}
        />
      </div>
    </div>
  );
};
