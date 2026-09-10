// ============================================================================
// CORTEX — Global type declarations
// ============================================================================

import type { cortexBridge } from './shared/types/ipc';

declare global {
  interface Window {
    cortexBridge?: cortexBridge;
  }

  interface ImportMetaEnv {
    VITE_PROXY_URL?: string;
    [key: string]: unknown;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}
