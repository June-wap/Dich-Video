import type { SystemDiagnostics } from './types';

export const diagnosticsService = {
  async getDiagnostics(): Promise<SystemDiagnostics> {
    return Promise.resolve({
      gpu: 'NVIDIA GeForce RTX 4050 (6GB GDDR6)',
      vramUsedGb: 1.8,
      vramTotalGb: 6.0,
      ramUsedGb: 6.4,
      ramTotalGb: 16.0,
      cudaStatus: 'CUDA Available (v12.4, Compute 8.9)',
      engineStatus: 'OmniVoice Ready (Local Core v1)',
      modelStatus: 'Model Loaded (vi_voice_v1.onnx)',
      pythonVersion: 'Python 3.12.3 (64-bit Virtualenv)',
      audioSpec: '24 kHz Mono (16-bit PCM)',
      isMock: true,
    });
  },
};
