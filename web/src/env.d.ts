/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_TARGET?: string
  readonly VITE_ANTI_DEBUG?: string
  readonly VITE_DISABLE_CONSOLE?: string
  readonly VITE_DISABLE_CONTEXT_MENU?: string
  readonly VITE_DISABLE_DEVTOOLS?: string
  readonly VITE_DISABLE_SELECTION?: string
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
