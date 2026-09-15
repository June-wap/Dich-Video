export type ComponentSize = 'sm' | 'md' | 'lg';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';

export type StatusVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

export type ComponentState = 'default' | 'hover' | 'focus' | 'disabled' | 'loading' | 'error';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}
