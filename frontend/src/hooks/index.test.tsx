import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useKeyDown } from './index';

function EscapeShortcut({ onEscape }: { onEscape: () => void }) {
  useKeyDown('Escape', onEscape);
  return null;
}

describe('useKeyDown', () => {
  it('does not run a shortcut while an IME composition is active, then resumes afterwards', () => {
    const onEscape = vi.fn();
    render(<EscapeShortcut onEscape={onEscape} />);

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', isComposing: true }));
    expect(onEscape).not.toHaveBeenCalled();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onEscape).toHaveBeenCalledTimes(1);
  });
});
