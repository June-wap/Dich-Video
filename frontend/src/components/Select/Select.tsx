import React, { forwardRef } from 'react';
import type { SelectOption } from '../../types';
import { cn } from '../../utils';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(({
  label,
  hint,
  error,
  options,
  placeholder,
  disabled = false,
  required = false,
  className,
  id,
  children,
  ...props
}, ref) => {
  const selectId = id || (label ? `select-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const hasError = Boolean(error);

  return (
    <div className={cn('ds-form-group', hasError && 'ds-control--error')}>
      {label && (
        <label htmlFor={selectId} className={cn('ds-label', required && 'ds-label--required')}>
          {label}
        </label>
      )}
      <div className="ds-control-wrapper">
        <select
          ref={ref}
          id={selectId}
          disabled={disabled}
          required={required}
          className={cn('ds-select', className)}
          aria-invalid={hasError}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
          {children}
        </select>
      </div>
      {error && <span className="ds-error-text">{error}</span>}
      {!error && hint && <span className="ds-hint">{hint}</span>}
    </div>
  );
});

Select.displayName = 'Select';
