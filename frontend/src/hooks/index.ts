import { useState, useEffect } from 'react';

/**
 * Hook to detect keydown events like Escape
 */
export function useKeyDown(targetKey: string, handler: () => void, enabled: boolean = true) {
  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === targetKey) {
        handler();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [targetKey, handler, enabled]);
}

/**
 * Hook for local modal or boolean disclosure state
 */
export function useDisclosure(initialState: boolean = false) {
  const [isOpen, setIsOpen] = useState(initialState);
  const open = () => setIsOpen(true);
  const close = () => setIsOpen(false);
  const toggle = () => setIsOpen((prev) => !prev);

  return { isOpen, open, close, toggle, setIsOpen };
}

/**
 * Hook for global Developer Mode setting (defaults to false / OFF)
 */
export function useDeveloperMode() {
  const [isDevMode, setIsDevMode] = useState<boolean>(() => {
    try {
      return localStorage.getItem('omnivoice_dev_mode') === 'true';
    } catch {
      return false;
    }
  });

  const setDevMode = (val: boolean) => {
    setIsDevMode(val);
    try {
      localStorage.setItem('omnivoice_dev_mode', String(val));
      window.dispatchEvent(new Event('dev_mode_change'));
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const handleStorageChange = () => {
      try {
        setIsDevMode(localStorage.getItem('omnivoice_dev_mode') === 'true');
      } catch {
        setIsDevMode(false);
      }
    };
    window.addEventListener('dev_mode_change', handleStorageChange);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('dev_mode_change', handleStorageChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return { isDevMode, setDevMode };
}
