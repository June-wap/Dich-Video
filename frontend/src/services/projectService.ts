import type { ProjectItem } from './types';

const MOCK_PROJECTS: ProjectItem[] = [
  {
    id: 'proj-001',
    name: 'Chương 1: Bình minh trên thảo nguyên',
    type: 'Long-form',
    voice: 'Hoài My (Nữ Miền Bắc)',
    language: 'Vietnamese',
    status: 'COMPLETED',
    progress: 100,
    updatedAt: '10 phút trước',
    route: '/long-form/proj-001',
  },
  {
    id: 'proj-002',
    name: 'Lời chào tiếp thị sản phẩm',
    type: 'Text to Speech',
    voice: 'Nam Anh (Nam Miền Bắc)',
    language: 'Vietnamese',
    status: 'COMPLETED',
    progress: 100,
    updatedAt: '35 phút trước',
    route: '/tts',
  },
  {
    id: 'proj-003',
    name: 'Audiobook: Lịch sử văn minh thế giới - Phần 2',
    type: 'Long-form',
    voice: 'Mai Thảo (Nữ Miền Nam)',
    language: 'Vietnamese',
    status: 'RUNNING',
    progress: 68,
    updatedAt: 'Vừa xong',
    route: '/long-form/proj-003',
  },
  {
    id: 'proj-004',
    name: 'Kịch bản đàm thoại công sở song ngữ Anh-Việt',
    type: 'Long-form',
    voice: 'Jenny & Mai Thảo',
    language: 'English',
    status: 'PAUSED',
    progress: 42,
    updatedAt: '2 giờ trước',
    route: '/long-form/proj-004',
  },
  {
    id: 'proj-005',
    name: 'Mẫu nhân bản giọng đọc bản tin thời sự',
    type: 'Voice Clone',
    voice: 'Custom Speaker Zero-Shot',
    language: 'Vietnamese',
    status: 'COMPLETED',
    progress: 100,
    updatedAt: 'Hôm qua',
    route: '/clone',
  },
  {
    id: 'proj-006',
    name: 'Báo cáo tài chính quý 3 tổng hợp âm thanh',
    type: 'Long-form',
    voice: 'Minh Quang (Nam Miền Nam)',
    language: 'Vietnamese',
    status: 'FAILED',
    progress: 25,
    updatedAt: '3 ngày trước',
    route: '/long-form/proj-006',
  },
  {
    id: 'proj-007',
    name: 'Hướng dẫn cài đặt hệ điều hành Linux cơ bản',
    type: 'Text to Speech',
    voice: 'Guy Studio (US Confident)',
    language: 'English',
    status: 'COMPLETED',
    progress: 100,
    updatedAt: '5 ngày trước',
    route: '/tts',
  },
];

let projectsCache = [...MOCK_PROJECTS];

export const projectService = {
  async getProjects(): Promise<ProjectItem[]> {
    return Promise.resolve([...projectsCache]);
  },

  async getProjectById(id: string): Promise<ProjectItem | undefined> {
    return Promise.resolve(projectsCache.find((p) => p.id === id));
  },

  async toggleProjectPause(id: string): Promise<boolean> {
    projectsCache = projectsCache.map((p) => {
      if (p.id === id) {
        return {
          ...p,
          status: p.status === 'PAUSED' ? 'RUNNING' : 'PAUSED',
        };
      }
      return p;
    });
    return Promise.resolve(true);
  },

  async renameProject(id: string, newName: string): Promise<boolean> {
    projectsCache = projectsCache.map((p) => (p.id === id ? { ...p, name: newName } : p));
    return Promise.resolve(true);
  },

  async deleteProject(id: string): Promise<boolean> {
    projectsCache = projectsCache.filter((p) => p.id !== id);
    return Promise.resolve(true);
  },
};
