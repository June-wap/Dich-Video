/**
 * Minimal, real i18n: a plain key -> string dictionary per locale and a
 * useT() hook, driven by Settings > General > Ngôn ngữ ứng dụng
 * (AppSettingsContext, see ../context/AppSettingsContext.tsx). No new
 * dependency (react-i18next etc.) - this app only ever needs two flat
 * dictionaries.
 *
 * SCOPE: this pass covers the app chrome (Sidebar, the Dashboard headers/
 * cards) and the entire Settings page - the two places a language switch is
 * immediately visible and the tab the switch itself lives in. TTS/Voice
 * Cloning/Voices/History page content stays Vietnamese-only for now; keys
 * for those can be added the same way later without changing this file's
 * shape. This is a deliberate scoping decision (see the project's Settings
 * overhaul notes), not a bug - switching to English does not silently
 * mistranslate anything, it just leaves untranslated pages in Vietnamese.
 */
import React, { createContext, useContext, useMemo } from 'react';

export type Locale = 'vi' | 'en';

type Dict = Record<string, string>;

const vi: Dict = {
  'app.brand': 'Voca Basic',
  'app.offlineEngine': 'Công cụ chạy cục bộ (Offline)',

  'nav.dashboard': 'Dashboard',
  'nav.section.create': 'TẠO MỚI',
  'nav.section.library': 'THƯ VIỆN',
  'nav.section.activity': 'HOẠT ĐỘNG',
  'nav.section.system': 'HỆ THỐNG',
  'nav.tts': 'Chuyển văn bản thành giọng nói',
  'nav.clone': 'Nhân bản giọng nói',
  'nav.voices': 'Giọng đọc',
  'nav.history': 'Lịch sử',
  'nav.settings': 'Cài đặt',
  'nav.diagnostics': 'Chẩn đoán',
  'sidebar.status.gpu': 'GPU',
  'sidebar.status.version': 'Phiên bản',
  'sidebar.status.ready': 'Sẵn sàng',
  'sidebar.status.notReady': 'Chưa sẵn sàng',
  'sidebar.status.unknown': 'Không xác định',
  'sidebar.status.notDetected': 'Không phát hiện GPU',

  'dashboard.greeting': 'Xin chào',
  'dashboard.subtitle': 'Bạn muốn tạo gì hôm nay?',
  'dashboard.status.cudaAvailable': 'CUDA khả dụng',
  'dashboard.status.cudaUnavailable': 'CUDA không khả dụng',
  'dashboard.card.tts.title': 'Text to Speech',
  'dashboard.card.tts.desc': 'Chuyển đổi văn bản thành giọng nói tức thì với các giọng đọc bản ngữ chất lượng cao.',
  'dashboard.card.tts.cta': 'Bắt đầu tạo',
  'dashboard.card.clone.title': 'Voice Cloning',
  'dashboard.card.clone.desc': 'Nhân bản giọng nói từ mẫu thu âm mẫu ngắn (zero-shot cloning) chạy cục bộ không gửi mạng.',
  'dashboard.card.clone.cta': 'Tạo mẫu giọng',
  'dashboard.card.voices.title': 'Voice Library',
  'dashboard.card.voices.desc': 'Kho quản lý các mô hình giọng nói đã cài đặt, tải thêm model hoặc cấu hình voice profile.',
  'dashboard.card.voices.cta': 'Khám phá thư viện',

  'settings.header.title': 'Settings (Cài đặt hệ thống)',
  'settings.header.subtitle': 'Cấu hình giao diện, phần cứng, tham số âm thanh và đường dẫn lưu trữ',
  'settings.save': 'Lưu thay đổi',
  'settings.saved': 'Đã lưu cài đặt',
  'settings.saveFailed': 'Không thể lưu cài đặt',
  'settings.loading': 'Đang tải cài đặt...',
  'settings.loadFailed': 'Không thể tải cài đặt. Kiểm tra kết nối tới backend cục bộ.',
  'settings.retry': 'Thử lại',

  'settings.tab.general': 'General (Chung)',
  'settings.tab.audio': 'Audio (Âm thanh)',
  'settings.tab.performance': 'Performance (Hiệu năng)',
  'settings.tab.storage': 'Storage (Lưu trữ)',
  'settings.tab.advanced': 'Advanced (Nâng cao)',
  'settings.tab.translation': 'Dịch máy (Gemini)',

  'settings.general.title': 'Cài đặt chung (General)',
  'settings.general.desc': 'Ngôn ngữ giao diện, chủ đề và thông báo người dùng',
  'settings.general.language.label': 'Ngôn ngữ ứng dụng (Language)',
  'settings.general.language.hint': 'Ngôn ngữ hiển thị trên thanh điều hướng, bảng Dashboard và trang Cài đặt. Các trang khác vẫn đang bằng tiếng Việt.',
  'settings.general.language.vi': 'Tiếng Việt (Mặc định)',
  'settings.general.language.en': 'English (US)',
  'settings.general.theme.label': 'Giao diện hiển thị (Theme)',
  'settings.general.theme.hint': 'Áp dụng ngay lập tức trên toàn bộ ứng dụng.',
  'settings.general.theme.light': 'Desktop Light (Workspace sáng chuẩn SaaS)',
  'settings.general.theme.dark': 'Dark Navy (Toàn bộ giao diện tối)',
  'settings.general.theme.system': 'Đồng bộ hệ điều hành',
  'settings.general.notifications.title': 'Thông báo & Âm thanh',
  'settings.general.notify.completion.title': 'Thông báo khi hoàn tất tác vụ',
  'settings.general.notify.completion.desc': 'Hiển thị thông báo hệ điều hành khi tạo giọng nói xong (yêu cầu cho phép thông báo trình duyệt).',
  'settings.general.notify.errors.title': 'Thông báo khi có lỗi',
  'settings.general.notify.errors.desc': 'Hiển thị thông báo hệ điều hành nếu tác vụ tạo giọng nói thất bại.',
  'settings.general.notify.permission.denied': 'Trình duyệt/ứng dụng đang chặn thông báo. Vào cài đặt hệ thống để cho phép.',
  'settings.general.notify.permission.request': 'Cho phép thông báo',
  'settings.general.update.title': 'Kiểm tra bản cập nhật',
  'settings.general.update.check': 'Kiểm tra bản mới',
  'settings.general.update.current': 'Phiên bản hiện tại',
  'settings.general.update.notConfigured': 'Chưa cấu hình kênh cập nhật cho bản dựng này - không thể kiểm tra bản mới tự động.',

  'settings.audio.title': 'Cài đặt âm thanh (Audio)',
  'settings.audio.desc': 'Định dạng xuất tệp, tần số lấy mẫu và căn chỉnh khoảng lặng',
  'settings.audio.format.label': 'Định dạng xuất (Output Format)',
  'settings.audio.format.hint': 'Áp dụng cho lần tạo giọng nói tiếp theo ở trang Text to Speech.',
  'settings.audio.format.wav': 'WAV (Lossless 24kHz Uncompressed)',
  'settings.audio.format.mp3': 'MP3 (Nén, dung lượng nhỏ hơn)',
  'settings.audio.format.both': 'WAV + MP3 (Xuất đồng thời cả 2 tệp)',
  'settings.audio.sampleRate.label': 'Sample Rate',
  'settings.audio.sampleRate.hint': 'Chuẩn studio tự nhiên cho giọng nói - cố định, không thể thay đổi.',
  'settings.audio.channels.label': 'Channels (Kênh âm thanh)',
  'settings.audio.channels.hint': 'Chuẩn tối ưu cho text-to-speech - cố định, không thể thay đổi.',
  'settings.audio.pause.label': 'Thời gian nghỉ ngắt câu (hiển thị)',
  'settings.audio.pause.hint': 'Lưu lại cùng cài đặt của bạn. Hiện chưa có tham số ngắt câu nào trong pipeline tổng hợp giọng nói để áp dụng giá trị này - xem ghi chú bên dưới.',
  'settings.audio.pause.notWired': 'Chưa có tác dụng: pipeline tổng hợp hiện không có tham số "khoảng lặng giữa câu" để điều chỉnh.',
  'settings.audio.silenceTrim.title': 'Tự động cắt khoảng lặng (Silence Trim)',
  'settings.audio.silenceTrim.desc': 'Lưu lại cùng cài đặt của bạn. Chưa có bước hậu xử lý cắt khoảng lặng trong pipeline hiện tại.',
  'settings.audio.outputDir.label': 'Thư mục lưu âm thanh xuất bản (Output Directory)',
  'settings.audio.outputDir.hint': 'Áp dụng ngay cho lần tạo giọng nói tiếp theo, không cần khởi động lại. Các tệp đã tạo trước đó vẫn phát được bình thường dù thư mục thay đổi.',
  'settings.audio.outputDir.reset': 'Đặt lại mặc định',
  'settings.audio.outputDir.browseUnavailable': 'Trình duyệt hộp thoại chọn thư mục của hệ điều hành không khả dụng trong ứng dụng web này - dán đường dẫn trực tiếp vào ô bên trên.',

  'settings.performance.title': 'Hiệu năng & Phần cứng (Performance)',
  'settings.performance.desc': 'Thiết bị tính toán và chính sách thử lại khi lỗi',
  'settings.performance.device.label': 'Bộ xử lý gia tốc (Compute Device)',
  'settings.performance.device.gpu.title': 'GPU CUDA (Khuyên dùng)',
  'settings.performance.device.gpu.desc': 'Sử dụng GPU CUDA đã cấu hình cho máy này.',
  'settings.performance.device.cpu.title': 'CPU (Thử nghiệm)',
  'settings.performance.device.cpu.desc': 'Chạy trên CPU - chậm hơn nhiều lần và chưa được kiểm định chất lượng đầu ra. Chỉ dùng khi không có GPU CUDA khả dụng.',
  'settings.performance.device.restartNote': 'Cần khởi động lại backend để áp dụng thay đổi thiết bị - không chuyển đổi được khi đang chạy.',
  'settings.performance.quality.label': 'Preset chất lượng hiển thị (Quality Preset)',
  'settings.performance.quality.hint': 'Đặt trực tiếp số bước khử nhiễu thực tế của mô hình (Nhanh = 8, Cân bằng = 16, Cao = 32) - số bước càng cao, âm thanh càng mượt nhưng tạo càng chậm. Bật "Chế độ nhà phát triển" ở tab Nâng cao nếu muốn tinh chỉnh số bước chính xác hơn 3 mức này.',
  'settings.performance.quality.fast': 'Fast',
  'settings.performance.quality.balanced': 'Balanced',
  'settings.performance.quality.high': 'High Quality',
  'settings.performance.retry.label': 'Số lần thử tối đa khi lỗi (Retry Count)',
  'settings.performance.retry.hint': 'Áp dụng thật cho cả Text to Speech và Long-form: tự động thử lại khi một lượt tổng hợp thất bại, trước khi báo lỗi.',
  'settings.performance.retry.1': '1 lần (không thử lại)',
  'settings.performance.retry.2': '2 lần (Mặc định khuyến nghị)',
  'settings.performance.retry.3': '3 lần',

  'settings.storage.title': 'Cơ sở dữ liệu & Lưu trữ (Storage)',
  'settings.storage.desc': 'Vị trí tệp SQLite thực tế và dung lượng âm thanh đã tạo',
  'settings.storage.dbPath.label': 'Đường dẫn tệp cơ sở dữ liệu (SQLite Database Path)',
  'settings.storage.dbPath.hint': 'Vị trí thực tế trên đĩa - chỉ đọc.',
  'settings.storage.modelDir.label': 'Thư mục mô hình cục bộ (Model Checkpoints)',
  'settings.storage.modelDir.hint': 'Backend chưa cung cấp đường dẫn này dưới dạng cấu hình - vị trí được ứng dụng tự xử lý nội bộ khi tải mô hình, nên ở đây không hiển thị một đường dẫn giả định.',
  'settings.storage.usage.title': 'Dung lượng âm thanh đã tạo',
  'settings.storage.usage.desc': 'Tổng dung lượng thực tế của tất cả tệp trong thư mục xuất bản hiện tại.',
  'settings.storage.usage.note': 'Đây là các tệp âm thanh thật của khách hàng (được History tham chiếu để phát lại) - không phải bộ nhớ đệm tạm thời, nên không có nút "xoá tất cả" ở đây để tránh làm hỏng lịch sử phát lại. Hãy dọn dẹp thủ công trong Explorer nếu cần.',

  'settings.advanced.title': 'Nâng cao cho nhà phát triển (Advanced)',
  'settings.advanced.badge': 'Developer Section',
  'settings.advanced.desc': 'Cấu hình chuyên sâu thuật toán suy luận và nhật ký gỡ lỗi',
  'settings.advanced.devMode.title': 'Chế độ Nhà phát triển (Developer Mode)',
  'settings.advanced.devMode.desc': 'Mặc định TẮT (OFF). Khi BẬT, cho phép xem tiến độ chunk, số lần thử lại, mã lỗi, thông tin model, RTF và logs.',
  'settings.advanced.collapsed': 'Phần cài đặt dành cho nhà phát triển đang được thu gọn. Hãy bật công tắc phía trên để mở khóa các tham số kỹ thuật.',
  'settings.advanced.numSteps.label': 'Số bước khử nhiễu (num_step)',
  'settings.advanced.numSteps.hint': 'Áp dụng thật cho pipeline tổng hợp (Text to Speech và Long-form). Số bước cao hơn = chất lượng cao hơn nhưng chậm hơn.',
  'settings.advanced.numSteps.8': '8 steps (Siêu nhanh, độ chi tiết thấp)',
  'settings.advanced.numSteps.16': '16 steps (Chuẩn đề xuất)',
  'settings.advanced.numSteps.32': '32 steps (Chất lượng cao nhất, tốn GPU)',
  'settings.advanced.debugLogs.title': 'Detailed Debug Logging',
  'settings.advanced.debugLogs.desc': 'Áp dụng thật ngay lập tức: chuyển mức log của backend sang DEBUG. Xem nhật ký thực tế tại trang Diagnostics.',
  'settings.advanced.saveAdvanced': 'Lưu cấu hình nâng cao',

  'settings.translation.title': 'Dịch máy trước khi đọc (Gemini)',
  'settings.translation.configured': 'Đã cấu hình',
  'settings.translation.notConfigured': 'Chưa cấu hình',
};

const en: Dict = {
  'app.brand': 'Voca Basic',
  'app.offlineEngine': 'Local Offline Engine',

  'nav.dashboard': 'Dashboard',
  'nav.section.create': 'CREATE',
  'nav.section.library': 'LIBRARY',
  'nav.section.activity': 'ACTIVITY',
  'nav.section.system': 'SYSTEM',
  'nav.tts': 'Text to Speech',
  'nav.clone': 'Voice Cloning',
  'nav.voices': 'Voices',
  'nav.history': 'History',
  'nav.settings': 'Settings',
  'nav.diagnostics': 'Diagnostics',
  'sidebar.status.gpu': 'GPU',
  'sidebar.status.version': 'Version',
  'sidebar.status.ready': 'Ready',
  'sidebar.status.notReady': 'Not ready',
  'sidebar.status.unknown': 'Unknown',
  'sidebar.status.notDetected': 'No GPU detected',

  'dashboard.greeting': 'Hello',
  'dashboard.subtitle': 'What would you like to create today?',
  'dashboard.status.cudaAvailable': 'CUDA available',
  'dashboard.status.cudaUnavailable': 'CUDA unavailable',
  'dashboard.card.tts.title': 'Text to Speech',
  'dashboard.card.tts.desc': 'Convert text into natural-sounding speech instantly with high-quality native voices.',
  'dashboard.card.tts.cta': 'Start creating',
  'dashboard.card.clone.title': 'Voice Cloning',
  'dashboard.card.clone.desc': 'Clone a voice from a short reference sample (zero-shot cloning), running fully offline.',
  'dashboard.card.clone.cta': 'Create a voice sample',
  'dashboard.card.voices.title': 'Voice Library',
  'dashboard.card.voices.desc': 'Manage installed voice models, add more, or configure voice profiles.',
  'dashboard.card.voices.cta': 'Browse library',

  'settings.header.title': 'Settings',
  'settings.header.subtitle': 'Interface, hardware, audio parameters and storage paths',
  'settings.save': 'Save changes',
  'settings.saved': 'Settings saved',
  'settings.saveFailed': 'Could not save settings',
  'settings.loading': 'Loading settings...',
  'settings.loadFailed': 'Could not load settings. Check the connection to the local backend.',
  'settings.retry': 'Retry',

  'settings.tab.general': 'General',
  'settings.tab.audio': 'Audio',
  'settings.tab.performance': 'Performance',
  'settings.tab.storage': 'Storage',
  'settings.tab.advanced': 'Advanced',
  'settings.tab.translation': 'Machine Translation (Gemini)',

  'settings.general.title': 'General settings',
  'settings.general.desc': 'Interface language, theme and notifications',
  'settings.general.language.label': 'Application language',
  'settings.general.language.hint': 'Applies to the navigation bar, Dashboard and Settings page. Other pages are still in Vietnamese.',
  'settings.general.language.vi': 'Vietnamese (Default)',
  'settings.general.language.en': 'English (US)',
  'settings.general.theme.label': 'Theme',
  'settings.general.theme.hint': 'Applies immediately across the whole app.',
  'settings.general.theme.light': 'Desktop Light (standard SaaS light workspace)',
  'settings.general.theme.dark': 'Dark Navy (fully dark interface)',
  'settings.general.theme.system': 'Match system',
  'settings.general.notifications.title': 'Notifications & sound',
  'settings.general.notify.completion.title': 'Notify when a task finishes',
  'settings.general.notify.completion.desc': 'Show an OS notification when speech generation completes (browser notification permission required).',
  'settings.general.notify.errors.title': 'Notify on errors',
  'settings.general.notify.errors.desc': 'Show an OS notification if a speech generation task fails.',
  'settings.general.notify.permission.denied': 'Notifications are currently blocked - allow them in your system/browser settings.',
  'settings.general.notify.permission.request': 'Allow notifications',
  'settings.general.update.title': 'Check for updates',
  'settings.general.update.check': 'Check now',
  'settings.general.update.current': 'Current version',
  'settings.general.update.notConfigured': 'No update channel is configured for this build - automatic update checks are not available.',

  'settings.audio.title': 'Audio settings',
  'settings.audio.desc': 'Output format, sample rate and silence handling',
  'settings.audio.format.label': 'Output format',
  'settings.audio.format.hint': 'Applies to the next generation on the Text to Speech page.',
  'settings.audio.format.wav': 'WAV (lossless, 24kHz, uncompressed)',
  'settings.audio.format.mp3': 'MP3 (compressed, smaller files)',
  'settings.audio.format.both': 'WAV + MP3 (write both files)',
  'settings.audio.sampleRate.label': 'Sample rate',
  'settings.audio.sampleRate.hint': 'Fixed studio-natural rate for speech - not configurable.',
  'settings.audio.channels.label': 'Channels',
  'settings.audio.channels.hint': 'Fixed, optimal for text-to-speech - not configurable.',
  'settings.audio.pause.label': 'Sentence pause length (display only)',
  'settings.audio.pause.hint': 'Saved with your settings. The synthesis pipeline has no pause-length parameter to apply this to yet - see the note below.',
  'settings.audio.pause.notWired': 'Not yet wired: the synthesis pipeline has no "pause between sentences" parameter to control.',
  'settings.audio.silenceTrim.title': 'Trim silence automatically',
  'settings.audio.silenceTrim.desc': 'Saved with your settings. There is no silence-trimming post-processing step in the pipeline yet.',
  'settings.audio.outputDir.label': 'Audio output directory',
  'settings.audio.outputDir.hint': 'Takes effect on the very next generation, no restart needed. Files already generated remain playable even after this changes.',
  'settings.audio.outputDir.reset': 'Reset to default',
  'settings.audio.outputDir.browseUnavailable': "This web app can't open the OS folder picker - paste the path directly into the field above.",

  'settings.performance.title': 'Performance & hardware',
  'settings.performance.desc': 'Compute device and retry policy',
  'settings.performance.device.label': 'Compute device',
  'settings.performance.device.gpu.title': 'GPU / CUDA (recommended)',
  'settings.performance.device.gpu.desc': "Use this machine's configured CUDA GPU.",
  'settings.performance.device.cpu.title': 'CPU (experimental)',
  'settings.performance.device.cpu.desc': 'Runs on CPU - much slower and not verified for output quality. Only use this when no CUDA GPU is available.',
  'settings.performance.device.restartNote': 'Requires a backend restart to take effect - cannot be hot-swapped while running.',
  'settings.performance.quality.label': 'Quality preset (display only)',
  'settings.performance.quality.hint': 'Directly sets the model\'s real denoising step count (Fast = 8, Balanced = 16, High = 32) - more steps means smoother audio but slower generation. Turn on "Developer mode" under Advanced to fine-tune the step count beyond these three presets.',
  'settings.performance.quality.fast': 'Fast',
  'settings.performance.quality.balanced': 'Balanced',
  'settings.performance.quality.high': 'High Quality',
  'settings.performance.retry.label': 'Retry count on failure',
  'settings.performance.retry.hint': 'Really applied to both Text to Speech and Long-form: automatically retries a failed synthesis attempt before reporting an error.',
  'settings.performance.retry.1': '1 (no retry)',
  'settings.performance.retry.2': '2 (recommended default)',
  'settings.performance.retry.3': '3',

  'settings.storage.title': 'Database & storage',
  'settings.storage.desc': 'Real SQLite file location and generated-audio disk usage',
  'settings.storage.dbPath.label': 'SQLite database path',
  'settings.storage.dbPath.hint': 'Actual location on disk - read only.',
  'settings.storage.modelDir.label': 'Local model checkpoints folder',
  'settings.storage.modelDir.hint': "Not exposed by the backend as a setting - resolved internally when the model loads, so no path is shown here instead of guessing one.",
  'settings.storage.usage.title': 'Generated audio disk usage',
  'settings.storage.usage.desc': 'Real total size of every file in the current output directory.',
  'settings.storage.usage.note': "These are your customer's real audio files (referenced by History for playback) - not a disposable cache, so there is deliberately no blanket \"clear\" button here to avoid breaking playback history. Clean up manually in File Explorer if needed.",

  'settings.advanced.title': 'Advanced (developer)',
  'settings.advanced.badge': 'Developer Section',
  'settings.advanced.desc': 'Deep inference tuning and debug logging',
  'settings.advanced.devMode.title': 'Developer Mode',
  'settings.advanced.devMode.desc': 'OFF by default. When ON, shows chunk progress, retries, error codes, model info, RTF and logs.',
  'settings.advanced.collapsed': 'Developer settings are collapsed. Turn on the switch above to unlock the technical parameters.',
  'settings.advanced.numSteps.label': 'Denoising steps (num_step)',
  'settings.advanced.numSteps.hint': 'Really applied to the synthesis pipeline (Text to Speech and Long-form). Higher = better quality but slower.',
  'settings.advanced.numSteps.8': '8 steps (fastest, lowest detail)',
  'settings.advanced.numSteps.16': '16 steps (recommended default)',
  'settings.advanced.numSteps.32': '32 steps (highest quality, more GPU)',
  'settings.advanced.debugLogs.title': 'Detailed debug logging',
  'settings.advanced.debugLogs.desc': "Really applied immediately: switches the backend's log level to DEBUG. See real output on the Diagnostics page.",
  'settings.advanced.saveAdvanced': 'Save advanced settings',

  'settings.translation.title': 'Machine translation (Gemini)',
  'settings.translation.configured': 'Configured',
  'settings.translation.notConfigured': 'Not configured',
};

const DICTS: Record<Locale, Dict> = { vi, en };

interface I18nValue {
  locale: Locale;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nValue>({ locale: 'vi', t: (key) => DICTS.vi[key] ?? key });

export const I18nProvider: React.FC<{ locale: Locale; children: React.ReactNode }> = ({ locale, children }) => {
  const value = useMemo<I18nValue>(() => ({
    locale,
    t: (key: string) => DICTS[locale]?.[key] ?? DICTS.vi[key] ?? key,
  }), [locale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export function useT() {
  return useContext(I18nContext);
}
