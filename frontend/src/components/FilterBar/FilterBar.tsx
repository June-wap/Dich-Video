import React from 'react';
import { cn } from '../../utils';

export interface FilterOption {
  id: string;
  label: string;
  count?: number;
}

export interface FilterBarProps {
  options: FilterOption[];
  activeId: string;
  onSelect: (id: string) => void;
  className?: string;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  options,
  activeId,
  onSelect,
  className,
}) => {
  return (
    <div className={cn('ds-tabs-list', className)} style={{ overflowX: 'auto', maxWidth: '100%' }}>
      {options.map((opt) => {
        const isActive = opt.id === activeId;
        return (
          <button
            key={opt.id}
            type="button"
            className={cn('ds-tab-trigger', isActive && 'ds-tab-trigger--active')}
            onClick={() => onSelect(opt.id)}
          >
            <span>{opt.label}</span>
            {typeof opt.count === 'number' && (
              <span
                style={{
                  marginLeft: '6px',
                  fontSize: '11px',
                  padding: '1px 6px',
                  borderRadius: '10px',
                  backgroundColor: isActive ? 'var(--neutral-100)' : 'rgba(0,0,0,0.06)',
                  color: isActive ? 'var(--color-primary-700)' : 'inherit',
                  fontWeight: 600,
                }}
              >
                {opt.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
