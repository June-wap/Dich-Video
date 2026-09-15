import React, { useEffect } from 'react';
import { cn } from '../../utils';
import { useKeyDown } from '../../hooks';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closeOnBackdrop?: boolean;
  closeOnEsc?: boolean;
  className?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
  closeOnEsc = true,
  className,
}) => {
  useKeyDown('Escape', onClose, isOpen && closeOnEsc);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="ds-modal-backdrop"
      onClick={closeOnBackdrop ? onClose : undefined}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      <div
        className={cn('ds-modal-panel', `ds-modal-panel--${size}`, className)}
        onClick={(e) => e.stopPropagation()}
      >
        {(title || description) && (
          <div className="ds-modal-header">
            <div className="ds-modal-header-content">
              {title && (
                <h2 id="modal-title" className="ds-modal-title">
                  {title}
                </h2>
              )}
              {description && <p className="ds-modal-description">{description}</p>}
            </div>
            <button
              className="ds-modal-close-btn"
              onClick={onClose}
              aria-label="Close modal"
              type="button"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        )}
        <div className="ds-modal-body">{children}</div>
        {footer && <div className="ds-modal-footer">{footer}</div>}
      </div>
    </div>
  );
};
