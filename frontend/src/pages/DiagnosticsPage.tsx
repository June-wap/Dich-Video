import React, { useCallback, useEffect, useState } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  StatusBadge,
  Modal,
  ErrorState,
} from '../components';
import { systemService } from '../services/systemService';
import type { SystemStatus } from '../services/systemService';
import { healthService } from '../services/healthService';

/**
 * Task 12: this page used to be 100% invented data (a hardcoded "RTX 4050",
 * fake VRAM/RAM gauges that never moved, a setInterval-animated fake "Self
 * Test" that always passed, and a fixed sample log transcript from
 * 2026-09-14 that was the same for every machine). Every value below now
 * comes from a real backend call:
 * - GET /api/system/status (backend/api/system.py) for hardware/runtime facts.
 * - GET /api/system/logs (new this pass - backend/logging_config.py's
 *   in-memory ring buffer, see get_recent_logs()) for real backend log lines.
 * - GET /api/health for the real running version string.
 *
 * There is deliberately no VRAM/RAM usage gauge here anymore: the backend's
 * SystemStatus schema does not report live GPU/RAM memory usage (adding it
 * would also have broken test_system_schema_cache_and_no_internal_fields'
 * exact-shape assertion - see this session's notes), so rather than half-fake
 * it, this page simply doesn't claim to show it. The "Self Test" is now a
 * real (if modest) connectivity check: it re-fetches /api/system/status and
 * /api/health live and reports what actually came back, instead of an
 * animated checklist that always ends in "All Checks Passed" regardless of
 * whether a backend is even running.
 */

type CheckResult = 'PASS' | 'FAIL' | 'INFO';

interface SelfTestStep {
  name: string;
  result: CheckResult;
  detail: string;
}

function formatTimestamp(date: Date): string {
  return date.toLocaleString('vi-VN', { hour12: false });
}

export const DiagnosticsPage: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [version, setVersion] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const [statusData, healthData] = await Promise.all([
        systemService.status(),
        healthService.get().catch(() => null),
      ]);
      setStatus(statusData);
      if (healthData) setVersion(healthData.version);
      setLastFetchedAt(new Date());
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : 'Không thể kết nối tới backend cục bộ.');
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  // Self test: a real, synchronous evaluation of the status just fetched -
  // no animation, no fixed durations, no step that can "pass" independently
  // of what the backend actually reported.
  const [selfTestSteps, setSelfTestSteps] = useState<SelfTestStep[] | null>(null);
  const [isRunningTest, setIsRunningTest] = useState(false);

  const runSelfTest = useCallback(async () => {
    setIsRunningTest(true);
    try {
      const [statusData, healthData] = await Promise.all([
        systemService.status().catch(() => null),
        healthService.get().catch(() => null),
      ]);
      setStatus(statusData);
      if (healthData) setVersion(healthData.version);
      setLastFetchedAt(new Date());

      const steps: SelfTestStep[] = [];
      steps.push(
        healthData
          ? { name: 'Kết nối backend cục bộ (GET /api/health)', result: 'PASS', detail: `v${healthData.version}` }
          : { name: 'Kết nối backend cục bộ (GET /api/health)', result: 'FAIL', detail: 'Không có phản hồi' }
      );
      if (statusData) {
        steps.push({
          name: 'Truy vấn trạng thái hệ thống (GET /api/system/status)',
          result: 'PASS',
          detail: statusData.status,
        });
        steps.push(
          statusData.cuda_available
            ? { name: 'CUDA / GPU', result: 'PASS', detail: statusData.gpu_name ?? 'Đã phát hiện GPU' }
            : { name: 'CUDA / GPU', result: 'INFO', detail: 'Không khả dụng - có thể đang chạy ở chế độ CPU thử nghiệm' }
        );
        steps.push(
          statusData.primary_provider
            ? { name: 'TTS provider', result: 'INFO', detail: `Trạng thái: ${statusData.provider_state}` }
            : { name: 'TTS provider', result: 'INFO', detail: 'Chưa có provider được cấu hình' }
        );
        steps.push({
          name: 'Cấu hình audio pipeline',
          result: 'INFO',
          detail: `${statusData.audio.sample_rate.toLocaleString('vi-VN')} Hz, ${statusData.audio.channels} kênh (cố định theo thiết kế, không đo tại đây)`,
        });
      } else {
        steps.push({
          name: 'Truy vấn trạng thái hệ thống (GET /api/system/status)',
          result: 'FAIL',
          detail: 'Không có phản hồi',
        });
      }
      setSelfTestSteps(steps);
    } finally {
      setIsRunningTest(false);
    }
  }, []);

  // Copy diagnostics JSON to clipboard - built from whatever was actually
  // fetched, honestly reporting null/unknown fields instead of inventing them.
  const [copiedNotification, setCopiedNotification] = useState(false);
  const handleCopyDiagnostics = () => {
    const report = {
      timestamp: new Date().toISOString(),
      fetched_at: lastFetchedAt?.toISOString() ?? null,
      backend_reachable: status !== null,
      version: version,
      status: status ?? { error: statusError ?? 'no data fetched' },
    };
    navigator.clipboard.writeText(JSON.stringify(report, null, 2)).then(() => {
      setCopiedNotification(true);
      setTimeout(() => setCopiedNotification(false), 2500);
    });
  };

  // Logs modal - real backend log lines (in-memory ring buffer, see
  // backend/logging_config.py's get_recent_logs(); never written to disk).
  const [isLogsOpen, setIsLogsOpen] = useState(false);
  const [logs, setLogs] = useState<string[] | null>(null);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const response = await systemService.logs();
      setLogs(response.logs);
    } catch (err) {
      setLogsError(err instanceof Error ? err.message : 'Không thể tải nhật ký.');
    } finally {
      setLogsLoading(false);
    }
  }, []);

  const handleOpenLogs = () => {
    setIsLogsOpen(true);
    void loadLogs();
  };

  const providerReady = Boolean(status?.primary_provider && status.provider_state === 'READY');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            Diagnostics (Chẩn đoán hệ thống)
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Trạng thái phần cứng, mô hình và nhật ký thực thi - lấy trực tiếp từ backend cục bộ
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {status && (
            <StatusBadge
              status={status.status === 'ready' ? 'success' : 'warning'}
              label={status.status === 'ready' ? 'Backend Ready' : 'Degraded'}
              size="sm"
            />
          )}
          <Button size="sm" variant="outline" onClick={handleCopyDiagnostics}>
            {copiedNotification ? 'Đã sao chép!' : 'Copy Diagnostics'}
          </Button>
          <Button size="sm" variant="outline" onClick={handleOpenLogs}>
            Xem nhật ký
          </Button>
          <Button size="sm" variant="primary" isLoading={isRunningTest} onClick={() => void runSelfTest()}>
            Kiểm tra kết nối
          </Button>
        </div>
      </div>

      {statusError && (
        <ErrorState
          title="Không thể kết nối tới backend cục bộ"
          message={statusError}
          retryLabel="Thử lại"
          onRetry={() => void loadStatus()}
        />
      )}

      {statusLoading && !status && !statusError && (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--neutral-500)', fontSize: '13px' }}>
          Đang tải trạng thái hệ thống...
        </div>
      )}

      {status && (
        <>
          {/* 6 Diagnostic Cards - every value is what /api/system/status just returned */}
          <div className="ds-diagnostics-grid">
            <div className="ds-diagnostic-card">
              <div className="ds-diagnostic-header">
                <span className="ds-diagnostic-title">GPU</span>
                <StatusBadge status={status.gpu_name ? 'success' : 'neutral'} label={status.gpu_name ? 'Đã phát hiện' : 'Không phát hiện'} size="sm" />
              </div>
              <div className="ds-diagnostic-value">{status.gpu_name ?? 'Không có GPU'}</div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                {status.gpu_name ? 'Từ torch.cuda.get_device_name()' : 'Có thể đang chạy CPU hoặc driver CUDA chưa sẵn sàng'}
              </span>
            </div>

            <div className="ds-diagnostic-card">
              <div className="ds-diagnostic-header">
                <span className="ds-diagnostic-title">CUDA</span>
                <StatusBadge status={status.cuda_available ? 'success' : 'neutral'} label={status.cuda_available ? 'Available' : 'Unavailable'} size="sm" />
              </div>
              <div className="ds-diagnostic-value">{status.cuda_available ? 'CUDA Available' : 'CUDA Unavailable'}</div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>torch: {status.torch_version ?? 'không xác định'}</span>
            </div>

            <div className="ds-diagnostic-card">
              <div className="ds-diagnostic-header">
                <span className="ds-diagnostic-title">TTS Provider</span>
                <StatusBadge status={providerReady ? 'success' : 'warning'} label={status.provider_state ?? 'UNAVAILABLE'} size="sm" />
              </div>
              <div className="ds-diagnostic-value">{providerReady ? 'Ready' : 'Unavailable'}</div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>Provider chính: {status.primary_provider ?? 'Chưa cấu hình'}</span>
            </div>

            <div className="ds-diagnostic-card">
              <div className="ds-diagnostic-header">
                <span className="ds-diagnostic-title">TTS availability</span>
                <StatusBadge status={providerReady ? 'success' : 'neutral'} label={providerReady ? 'Available' : 'Unavailable'} size="sm" />
              </div>
              <div className="ds-diagnostic-value">{providerReady ? 'Available' : 'Unavailable'}</div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                {providerReady ? 'Sẵn sàng tổng hợp' : 'Chưa có TTS provider'}
              </span>
            </div>

            <div className="ds-diagnostic-card">
              <div className="ds-diagnostic-header">
                <span className="ds-diagnostic-title">Python Runtime</span>
                <StatusBadge status="success" label="Active" size="sm" />
              </div>
              <div className="ds-diagnostic-value">Python {status.python_version}</div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>Ứng dụng: v{version ?? '—'}</span>
            </div>

            <div className="ds-diagnostic-card">
              <div className="ds-diagnostic-header">
                <span className="ds-diagnostic-title">Audio Pipeline</span>
                <StatusBadge status="success" label="Cố định" size="sm" />
              </div>
              <div className="ds-diagnostic-value">
                {status.audio.sample_rate.toLocaleString('vi-VN')} Hz, {status.audio.channels === 1 ? 'Mono' : `${status.audio.channels} kênh`}
              </div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                Cố định theo hợp đồng API (không cấu hình được) - không phải giá trị đo tại thời điểm này
              </span>
            </div>
          </div>

          {/* Self Test results - only shown after the user actually runs it */}
          {selfTestSteps && (
            <Card>
              <CardHeader>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <CardTitle>Kết quả kiểm tra kết nối</CardTitle>
                    <CardDescription>Gọi trực tiếp GET /api/health và GET /api/system/status - không mô phỏng</CardDescription>
                  </div>
                  <StatusBadge
                    status={selfTestSteps.some((s) => s.result === 'FAIL') ? 'error' : 'success'}
                    label={selfTestSteps.some((s) => s.result === 'FAIL') ? 'Có lỗi' : 'Tất cả đều ổn'}
                    size="sm"
                  />
                </div>
              </CardHeader>
              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {selfTestSteps.map((step, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 14px', background: 'var(--surface-subtle)',
                      borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <StatusBadge
                        status={step.result === 'PASS' ? 'success' : step.result === 'FAIL' ? 'error' : 'neutral'}
                        label={step.result}
                        size="sm"
                      />
                      <span style={{ fontSize: '13px', color: 'var(--neutral-800)', fontWeight: 500 }}>{step.name}</span>
                    </div>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{step.detail}</span>
                  </div>
                ))}
              </CardContent>
              <CardFooter>
                <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                  Lần kiểm tra gần nhất: {lastFetchedAt ? formatTimestamp(lastFetchedAt) : '—'}
                </span>
              </CardFooter>
            </Card>
          )}
        </>
      )}

      {/* Logs Viewer Modal - real in-memory backend log lines */}
      <Modal
        isOpen={isLogsOpen}
        onClose={() => setIsLogsOpen(false)}
        title="Nhật ký hệ thống (System Logs)"
        size="lg"
        footer={
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
              {logs ? `${logs.length} dòng gần nhất (bộ nhớ đệm, không ghi ra đĩa)` : ''}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button variant="outline" size="sm" onClick={() => void loadLogs()} disabled={logsLoading}>
                Làm mới
              </Button>
              <Button variant="outline" size="md" onClick={() => setIsLogsOpen(false)}>
                Đóng
              </Button>
            </div>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {logsError ? (
            <ErrorState title="Không thể tải nhật ký" message={logsError} retryLabel="Thử lại" onRetry={() => void loadLogs()} />
          ) : logsLoading ? (
            <div style={{ padding: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--neutral-500)' }}>Đang tải...</div>
          ) : logs && logs.length > 0 ? (
            <div className="ds-log-box">{logs.join('\n')}</div>
          ) : (
            <div style={{ padding: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--neutral-500)' }}>
              Chưa có dòng nhật ký nào trong bộ nhớ đệm (backend có thể vừa khởi động lại - bộ đệm không tồn tại qua lần khởi động lại).
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
