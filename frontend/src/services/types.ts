export interface TTSRequest {
  text: string;
  voice: string;
  language: string;
  quality: 'fast' | 'balanced' | 'high';
  speed: number;
}

export interface TTSResult {
  audioUrl: string;
  duration: number;
  format: 'wav' | 'mp3';
  latencyMs: number;
}

export interface VoiceItem {
  id: string;
  name: string;
  language: string;
  languageCode: string;
  type: 'Built-in' | 'Cloned' | 'Community';
  status: 'Verified' | 'Needs Review' | 'Unavailable';
  referenceDuration: string;
  lastUsed: string;
  description: string;
}

export interface ProjectItem {
  id: string;
  name: string;
  type: 'Text to Speech' | 'Long-form' | 'Voice Clone';
  voice: string;
  language: string;
  status: 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED';
  progress: number;
  updatedAt: string;
  route: string;
}

export interface HistoryItem {
  id: string;
  date: string;
  type: 'Text to Speech' | 'Long-form' | 'Voice Clone';
  textPreview: string;
  voice: string;
  language: string;
  duration: string;
  status: 'COMPLETED' | 'FAILED' | 'CANCELLED';
  dateCategory: 'today' | 'week' | 'month';
  route: string;
}

export interface SystemDiagnostics {
  gpu: string;
  vramUsedGb: number;
  vramTotalGb: number;
  ramUsedGb: number;
  ramTotalGb: number;
  cudaStatus: string;
  engineStatus: string;
  modelStatus: string;
  pythonVersion: string;
  audioSpec: string;
  isMock: boolean;
}
