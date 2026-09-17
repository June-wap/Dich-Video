import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// jsdom does not implement HTMLMediaElement playback internals; AudioPlayer's
// real <audio> element only needs its element to exist and accept src/onError
// in tests, never actual decoding, so these are stubbed to no-ops rather than
// left throwing "Not implemented" errors into every test that renders one.
if (typeof window !== 'undefined') {
  window.HTMLMediaElement.prototype.load = () => {};
  window.HTMLMediaElement.prototype.play = () => Promise.resolve();
  window.HTMLMediaElement.prototype.pause = () => {};
}

afterEach(() => {
  cleanup();
});
