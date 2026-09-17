import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../Button/Button';
import { StatusBadge } from '../StatusBadge/StatusBadge';
import type { TtsAudioFormat } from '../../services/ttsJobService';

export interface AudioPlayerProps {
  title?: string;
  duration?: number; // duration in seconds, default 18 - SimulatedAudioPlayer only
  voice?: string;
  language?: string;
  onDownloadWav?: () => void;
  onDownloadMp3?: () => void;
  onRegenerate?: () => void;
  className?: string;
  /**
   * A real, fetchable audio URL (already resolved via
   * ttsJobService.resolveAudioUrl - never reconstructed here). When present,
   * AudioPlayer renders RealAudioPlayer (a native <audio controls> element)
   * instead of the old simulated timeline. Absent - the default, and still
   * what every mock caller (LongFormPage, HistoryPage's modal) passes -
   * keeps the original SimulatedAudioPlayer behavior unchanged.
   */
  src?: string;
  /** Best-effort format label (WAV/MP3) for the RealAudioPlayer's badge and
   * download button text. Purely cosmetic - does not affect playback. */
  format?: TtsAudioFormat;
  /** Real playback error handler - fires when the browser fails to load the
   * given `src` (e.g. the backend audio artifact has since been deleted and
   * now 404s). Only meaningful together with `src`. */
  onError?: () => void;
}

/**
 * Dispatcher: real playback when a real `src` is supplied (Task 3's
 * persisted TTS Job API), the original mock/simulated player otherwise -
 * every existing caller that doesn't pass `src` keeps working unchanged.
 */
export const AudioPlayer: React.FC<AudioPlayerProps> = (props) => {
  if (props.src) {
    return <RealAudioPlayer {...props} src={props.src} />;
  }
  return <SimulatedAudioPlayer {...props} />;
};

/**
 * Real playback backed by an actual backend audio URL. Uses the native
 * <audio controls> element rather than extending the fully custom
 * fake-timeline player below: it gets real seeking, volume, and
 * keyboard/screen-reader accessibility from the browser for free, and needs
 * no fake duration/progress simulation - the browser already knows the
 * file's real duration once it loads.
 */
const RealAudioPlayer: React.FC<AudioPlayerProps & { src: string }> = ({
  title = 'Kết quả âm thanh',
  voice = 'Mặc định',
  language = 'Vietnamese',
  format,
  src,
  onError,
}) => {
  const formatLabel = format ? format.toUpperCase() : null;

  return (
    <div className="ds-audio-player">
      <div className="ds-audio-player-meta">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="ds-audio-player-title">{title}</span>
          {formatLabel && <StatusBadge status="success" label={formatLabel} size="sm" />}
        </div>

        <div className="ds-audio-player-tags">
          <StatusBadge status="neutral" label={`Voice: ${voice}`} size="sm" showDot={false} />
          <StatusBadge status="info" label={language} size="sm" showDot={false} />
        </div>
      </div>

      {/* Real, native playback - keyboard-accessible and screen-reader
          friendly out of the box, unlike the fully custom timeline below. */}
      <audio controls src={src} onError={onError} style={{ width: '100%', marginTop: '8px' }}>
        Trình duyệt của bạn không hỗ trợ phát tệp âm thanh.
      </audio>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '10px',
          marginTop: '10px',
        }}
      >
        {/* A real <a href download> rather than a JS-driven "Mock Download"
            handler - it downloads the actual backend artifact bytes. */}
        <a
          href={src}
          download
          className="ds-btn ds-btn--outline ds-btn--sm"
          style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          <span>Tải xuống {formatLabel ?? 'tệp âm thanh'}</span>
        </a>
      </div>
    </div>
  );
};

/**
 * Original fully-simulated fake-timeline player. Unchanged in behavior from
 * before Task 3 aside from the rename - preserved as-is for every caller
 * that has no real `src` (LongFormPage, HistoryPage's replay modal, and any
 * other mock flow not yet migrated to a real backend).
 */
const SimulatedAudioPlayer: React.FC<AudioPlayerProps> = ({
  title = 'Generated Audio Result',
  duration = 18.4,
  voice = 'vi-VN-HoaiMy',
  language = 'Vietnamese',
  onDownloadWav,
  onDownloadMp3,
  onRegenerate,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState<1 | 1.25 | 1.5 | 2>(1);
  const [isMuted, setIsMuted] = useState(false);

  const timerRef = useRef<number | null>(null);

  // Format seconds to mm:ss
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Simulated audio playback progression
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = 100;
      timerRef.current = window.setInterval(() => {
        setCurrentTime((prev) => {
          const next = prev + (intervalMs / 1000) * playbackSpeed;
          if (next >= duration) {
            setIsPlaying(false);
            return 0;
          }
          return next;
        });
      }, intervalMs);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, duration, playbackSpeed]);

  const togglePlay = () => {
    setIsPlaying(!isPlaying);
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    setCurrentTime(ratio * duration);
  };

  const cycleSpeed = () => {
    const speeds: (1 | 1.25 | 1.5 | 2)[] = [1, 1.25, 1.5, 2];
    const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    setPlaybackSpeed(speeds[nextIdx]);
  };

  const progressPercent = Math.min(100, Math.max(0, (currentTime / duration) * 100));

  return (
    <div className="ds-audio-player">
      {/* Meta header */}
      <div className="ds-audio-player-meta">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="ds-audio-player-title">{title}</span>
          <StatusBadge status="success" label="WAV 24kHz / 16-bit" size="sm" />
        </div>

        <div className="ds-audio-player-tags">
          <StatusBadge status="neutral" label={`Voice: ${voice}`} size="sm" showDot={false} />
          <StatusBadge status="info" label={language} size="sm" showDot={false} />
        </div>
      </div>

      {/* Main player controls & timeline */}
      <div className="ds-audio-player-main">
        {/* Play / Pause */}
        <button
          type="button"
          className="ds-player-play-btn"
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1"></rect>
              <rect x="14" y="4" width="4" height="16" rx="1"></rect>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ marginLeft: '2px' }}>
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          )}
        </button>

        {/* Timeline track */}
        <div className="ds-player-timeline">
          <div className="ds-player-scrubber-wrapper" onClick={handleSeek}>
            <div className="ds-player-track">
              <div
                className="ds-player-progress"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          <div className="ds-player-time">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        {/* Speed button */}
        <button
          type="button"
          className="ds-player-speed-btn"
          onClick={cycleSpeed}
          title="Playback speed"
        >
          {playbackSpeed}x
        </button>

        {/* Mute toggle */}
        <button
          type="button"
          onClick={() => setIsMuted(!isMuted)}
          className="ds-player-speed-btn"
          title={isMuted ? 'Unmute' : 'Mute'}
        >
          {isMuted ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="1" y1="1" x2="23" y2="23"></line>
              <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path>
              <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"></path>
              <line x1="12" y1="19" x2="12" y2="23"></line>
              <line x1="8" y1="23" x2="16" y2="23"></line>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
            </svg>
          )}
        </button>
      </div>

      {/* Export / Regenerate action bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', marginTop: '4px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="sm"
            variant="outline"
            onClick={onDownloadWav || (() => alert('Mock Download: exported_audio.wav'))}
            iconLeft={
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
            }
          >
            Download WAV
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={onDownloadMp3 || (() => alert('Mock Download: exported_audio.mp3'))}
            iconLeft={
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
            }
          >
            Download MP3
          </Button>
        </div>

        {onRegenerate && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onRegenerate}
            iconLeft={
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="1 4 1 10 7 10"></polyline>
                <polyline points="23 20 23 14 17 14"></polyline>
                <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path>
              </svg>
            }
          >
            Regenerate
          </Button>
        )}
      </div>
    </div>
  );
};
