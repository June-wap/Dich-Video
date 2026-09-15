import React, { forwardRef } from 'react';
import { cn } from '../../utils';

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(({
  label,
  hint,
  error,
  disabled = false,
  required = false,
  rows = 4,
  className,
  id,
  ...props
}, ref) => {
  const textareaId = id || (label ? `textarea-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const hasError = Boolean(error);

  return (
    <div className={cn('ds-form-group', hasError && 'ds-control--error')}>
      {label && (
        <label htmlFor={textareaId} className={cn('ds-label', required && 'ds-label--required')}>
          {label}
        </label>
      )}
      <div className="ds-control-wrapper">
        <textarea
          ref={ref}
          id={textareaId}
          disabled={disabled}
          required={required}
          rows={rows}
          className={cn('ds-textarea', className)}
          aria-invalid={hasError}
          {...props}
        />
      </div>
      {error && <span className="ds-error-text">{error}</span>}
      {!error && hint && <span className="ds-hint">{hint}</span>}
    </div>
  );
});

TextArea.displayName = 'TextArea';
