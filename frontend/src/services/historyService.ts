import type { HistoryItem } from './types';

const MOCK_HISTORY: HistoryItem[] = [
  {
    id: 'hist-001',
    date: '14/09/2026 11:42',
    type: 'Text to Speech',
    textPreview: 'Xin chào! Chào mừng bạn đến với OmniVoice Local AI Voice Studio...',
    voice: 'Hoài My (Nữ Miền Bắc)',
    language: 'Vietnamese',
    duration: '18.4s',
    status: 'COMPLETED',
    dateCategory: 'today',
    route: '/tts',
  },
  {
    id: 'hist-002',
    date: '14/09/2026 10:15',
    type: 'Long-form',
    textPreview: 'Mặt trời bắt đầu nhô lên khỏi rặng núi phía đông, rải những tia nắng ấm áp...',
    voice: 'Nam Anh (Nam Miền Bắc)',
    language: 'Vietnamese',
    duration: '18m 42s',
    status: 'COMPLETED',
    dateCategory: 'today',
    route: '/long-form/proj-001',
  },
  {
    id: 'hist-003',
    date: '14/09/2026 09:30',
    type: 'Voice Clone',
    textPreview: 'Xin kính chào quý thính giả, hôm nay chúng ta sẽ cùng tìm hiểu về...',
    voice: 'Giọng Đọc Mẫu Thảo',
    language: 'Vietnamese',
    duration: '14.2s',
    status: 'COMPLETED',
    dateCategory: 'today',
    route: '/clone',
  },
  {
    id: 'hist-004',
    date: '12/09/2026 16:20',
    type: 'Text to Speech',
    textPreview: 'Good morning ladies and gentlemen, welcome to our annual engineering keynote...',
    voice: 'Jenny Studio (US Natural)',
    language: 'English',
    duration: '24.1s',
    status: 'COMPLETED',
    dateCategory: 'week',
    route: '/tts',
  },
  {
    id: 'hist-005',
    date: '11/09/2026 14:05',
    type: 'Long-form',
    textPreview: 'Chương 2: Cơn bão trên đại ngàn và khúc ca biệt ly của những chiến binh...',
    voice: 'Minh Quang (Nam Miền Nam)',
    language: 'Vietnamese',
    duration: '12m 10s',
    status: 'CANCELLED',
    dateCategory: 'week',
    route: '/long-form',
  },
  {
    id: 'hist-006',
    date: '10/09/2026 08:50',
    type: 'Text to Speech',
    textPreview: 'Lỗi bộ nhớ đệm: Phân đoạn văn bản vượt quá kích thước buffer quy định...',
    voice: 'Mai Thảo (Nữ Miền Nam)',
    language: 'Vietnamese',
    duration: '--',
    status: 'FAILED',
    dateCategory: 'week',
    route: '/tts',
  },
  {
    id: 'hist-007',
    date: '28/08/2026 19:35',
    type: 'Long-form',
    textPreview: 'Toàn tập tiểu thuyết cổ điển: Những người khốn khổ - Khúc dạo đầu...',
    voice: 'Hoài My (Nữ Miền Bắc)',
    language: 'Vietnamese',
    duration: '45m 20s',
    status: 'COMPLETED',
    dateCategory: 'month',
    route: '/long-form',
  },
];

let historyCache = [...MOCK_HISTORY];

export const historyService = {
  async getHistory(): Promise<HistoryItem[]> {
    return Promise.resolve([...historyCache]);
  },

  async deleteHistoryItem(id: string): Promise<boolean> {
    historyCache = historyCache.filter((h) => h.id !== id);
    return Promise.resolve(true);
  },
};
