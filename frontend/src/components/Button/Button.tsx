import React from 'react';
import type { ButtonVariant, ComponentSize } from '../../types';
import { cn } from '../../utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ComponentSize;
  isLoading?: boolean;
  loadingText?: string;
  isError?: boolean;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loadingText,
  isError = false,
  disabled = false,
  iconLeft,
  iconRight,
  className,
  ...props
}) => {
  const isButtonDisabled = disabled || isLoading;

  return (
    <button
      className={cn(
        'ds-btn',
        `ds-btn--${variant}`,
        `ds-btn--${size}`,
        isLoading && 'ds-btn--loading',
        isError && 'ds-btn--danger',
        isButtonDisabled && 'ds-btn--disabled',
        className
      )}
      disabled={isButtonDisabled}
      aria-busy={isLoading}
      {...props}
    >
      {isLoading ? (
        <>
          <span className="ds-btn-spinner" aria-hidden="true" />
          {loadingText ? <span>{loadingText}</span> : children}
        </>
      ) : (
        <>
          {iconLeft && <span className="ds-btn-icon-left">{iconLeft}</span>}
          <span>{children}</span>
          {iconRight && <span className="ds-btn-icon-right">{iconRight}</span>}
        </>
      )}
    </button>
  );
};
