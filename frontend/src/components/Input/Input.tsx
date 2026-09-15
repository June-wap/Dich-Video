import React, { forwardRef } from 'react';
import { cn } from '../../utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  hint,
  error,
  isLoading = false,
  disabled = false,
  required = false,
  leftIcon,
  rightIcon,
  className,
  id,
  ...props
}, ref) => {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const hasError = Boolean(error);
  const hasLeftIcon = Boolean(leftIcon);
  const hasRightAffix = Boolean(rightIcon || isLoading);

  return (
    <div className={cn('ds-form-group', hasError && 'ds-control--error')}>
      {label && (
        <label htmlFor={inputId} className={cn('ds-label', required && 'ds-label--required')}>
          {label}
        </label>
      )}
      <div className="ds-control-wrapper">
        {leftIcon && <span className="ds-control-prefix">{leftIcon}</span>}
        <input
          ref={ref}
          id={inputId}
          disabled={disabled || isLoading}
          required={required}
          className={cn(
            'ds-input',
            hasLeftIcon && 'ds-input--has-prefix',
            hasRightAffix && 'ds-input--has-suffix',
            className
          )}
          aria-invalid={hasError}
          {...props}
        />
        {isLoading ? (
          <span className="ds-control-suffix">
            <span className="ds-btn-spinner" style={{ color: 'var(--neutral-400)' }} />
          </span>
        ) : rightIcon ? (
          <span className="ds-control-suffix">{rightIcon}</span>
        ) : null}
      </div>
      {error && <span className="ds-error-text">{error}</span>}
      {!error && hint && <span className="ds-hint">{hint}</span>}
    </div>
  );
});

Input.displayName = 'Input';
