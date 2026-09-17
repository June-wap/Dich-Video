/**
 * Real OS/browser notifications via the standard web Notification API. This
 * app is a plain React/Vite frontend (not Electron - see frontend/package.json,
 * there is no electron dependency), so the Notification API is the only
 * genuinely available mechanism for a desktop-style notification here, and it
 * does work from inside a Chromium-based WebView shell the same as in a
 * regular browser tab.
 *
 * Settings > General's "Thông báo khi hoàn tất tác vụ" / "Âm báo cảnh báo lỗi"
 * toggles (see AppSettingsContext) gate whether notify() is even attempted -
 * this module only wraps the permission/display mechanics.
 */

export type NotificationPermissionState = 'granted' | 'denied' | 'default' | 'unsupported';

export function getNotificationPermission(): NotificationPermissionState {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported';
  return Notification.permission;
}

export async function requestNotificationPermission(): Promise<NotificationPermissionState> {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported';
  try {
    const result = await Notification.requestPermission();
    return result;
  } catch {
    return 'denied';
  }
}

/**
 * Shows a real notification if and only if permission was already granted.
 * Never requests permission itself (that must be a deliberate user action -
 * see Settings > General) and never throws - a notification is a courtesy,
 * not something that should ever break the calling flow (e.g. a completed
 * TTS job) if the platform rejects it.
 */
export function notify(title: string, body?: string): void {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  if (Notification.permission !== 'granted') return;
  try {
    new Notification(title, body ? { body } : undefined);
  } catch {
    // Some platforms (and most headless/test environments) throw on
    // construction even when permission looks granted - never let a
    // best-effort notification break the caller.
  }
}
