import type { VoiceItem } from './types';

const MOCK_VOICES: VoiceItem[] = [
  {
    id: 'v-01',
    name: 'Hoài My (Nữ Miền Bắc)',
    language: 'Vietnamese',
    languageCode: 'vi',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural (24kHz)',
    lastUsed: '10 phút trước',
    description: 'Giọng đọc chuẩn Hà Nội, ấm áp, truyền cảm, thích hợp đọc truyện và sách nói.',
  },
  {
    id: 'v-02',
    name: 'Nam Anh (Nam Miền Bắc)',
    language: 'Vietnamese',
    languageCode: 'vi',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural (24kHz)',
    lastUsed: '1 giờ trước',
    description: 'Giọng nam thanh lịch, rõ ràng, phù hợp cho tin tức, tài liệu khoa học và podcast.',
  },
  {
    id: 'v-03',
    name: 'Mai Thảo (Nữ Miền Nam)',
    language: 'Vietnamese',
    languageCode: 'vi',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural (24kHz)',
    lastUsed: 'Hôm qua',
    description: 'Giọng nữ Sài Gòn ngọt ngào, gần gũi, tự nhiên trong hội thoại đời sống.',
  },
  {
    id: 'v-04',
    name: 'Minh Quang (Nam Miền Nam)',
    language: 'Vietnamese',
    languageCode: 'vi',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural (24kHz)',
    lastUsed: '3 ngày trước',
    description: 'Giọng nam miền Nam chững chạc, nội lực, phù hợp thuyết minh phóng sự.',
  },
  {
    id: 'v-05',
    name: 'Thầy Minh (Giáo Trình)',
    language: 'Vietnamese',
    languageCode: 'vi',
    type: 'Cloned',
    status: 'Verified',
    referenceDuration: '14.2s Reference Sample',
    lastUsed: '2 giờ trước',
    description: 'Nhân bản từ mẫu thu âm bài giảng, ngữ điệu sư phạm chuẩn mực.',
  },
  {
    id: 'v-06',
    name: 'BTV Thời Sự 19h',
    language: 'Vietnamese',
    languageCode: 'vi',
    type: 'Cloned',
    status: 'Needs Review',
    referenceDuration: '8.4s Reference Sample',
    lastUsed: 'Chưa dùng',
    description: 'Mẫu nhân bản thử nghiệm phát thanh viên, cần thẩm định chất lượng.',
  },
  {
    id: 'v-07',
    name: 'Jenny Studio (US Natural)',
    language: 'English',
    languageCode: 'en',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural',
    lastUsed: 'Hôm qua',
    description: 'High fidelity American English female voice suitable for professional presentations.',
  },
  {
    id: 'v-08',
    name: 'Guy Studio (US Confident)',
    language: 'English',
    languageCode: 'en',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural',
    lastUsed: '4 ngày trước',
    description: 'Authoritative male narrator voice for commercial audiobooks and documentation.',
  },
  {
    id: 'v-09',
    name: 'Xiaoxiao (Mandarin)',
    language: 'Chinese',
    languageCode: 'zh',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural',
    lastUsed: 'Tuần trước',
    description: 'Standard Putonghua neural speaker with natural prosody and rhythm.',
  },
  {
    id: 'v-10',
    name: 'Nanami (Tokyo Standard)',
    language: 'Japanese',
    languageCode: 'ja',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural',
    lastUsed: 'Tuần trước',
    description: 'Clear, polite Japanese female speaker for conversational and audio instruction.',
  },
  {
    id: 'v-11',
    name: 'Elvira (Castilian)',
    language: 'Spanish',
    languageCode: 'es',
    type: 'Built-in',
    status: 'Verified',
    referenceDuration: 'Built-in Neural',
    lastUsed: '2 tuần trước',
    description: 'European Spanish native speaker with expressive cadence.',
  },
  {
    id: 'v-12',
    name: 'Denise (Parisian)',
    language: 'French',
    languageCode: 'fr',
    type: 'Community',
    status: 'Needs Review',
    referenceDuration: '22.0s Reference Sample',
    lastUsed: 'Chưa dùng',
    description: 'Community contributed French speaker model pending acoustic verification.',
  },
  {
    id: 'v-13',
    name: 'Legacy Kokoro v0.1 (Deprecated)',
    language: 'English',
    languageCode: 'en',
    type: 'Community',
    status: 'Unavailable',
    referenceDuration: 'Offline File Missing',
    lastUsed: '1 tháng trước',
    description: 'Model artifact checksum mismatch or weights removed from local disk.',
  },
];

let voicesCache = [...MOCK_VOICES];

export const voiceService = {
  async getVoices(): Promise<VoiceItem[]> {
    return Promise.resolve([...voicesCache]);
  },

  async getVoiceById(id: string): Promise<VoiceItem | undefined> {
    return Promise.resolve(voicesCache.find((v) => v.id === id));
  },

  async renameVoice(id: string, newName: string): Promise<boolean> {
    voicesCache = voicesCache.map((v) => (v.id === id ? { ...v, name: newName } : v));
    return Promise.resolve(true);
  },

  async deleteVoice(id: string): Promise<boolean> {
    voicesCache = voicesCache.filter((v) => v.id !== id);
    return Promise.resolve(true);
  },
};
