/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the API when frontend and backend are deployed separately. */
  readonly VITE_API_URL?: string;
  /** Hugging Face Space that reads photos on a GPU, e.g. "Jainil19/lectura".
   *  Takes precedence over VITE_API_URL for extraction. */
  readonly VITE_HF_SPACE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
