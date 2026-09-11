/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the API when frontend and backend are deployed separately. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
