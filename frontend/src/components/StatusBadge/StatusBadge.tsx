import React from 'react';
import type { StatusVariant } from '../../types';
import { cn } from '../../utils';

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusVariant;
  label: string;
  showDot?: boolean;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status = 'neutral',
  label,
  showDot = true,
  size = 'md',
  className,
  ...props
}) => {
  return (
    <span
      className={cn(
        'ds-badge',
        `ds-badge--${status}`,
        `ds-badge--${size}`,
        className
      )}
      {...props}
    >
      {showDot && <span className="ds-badge-dot" aria-hidden="true" />}
      <span>{label}</span>
    </span>
  );
};
