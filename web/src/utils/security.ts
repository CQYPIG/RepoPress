const noop = () => undefined

const CONSOLE_METHODS = [
  'assert', 'clear', 'count', 'countReset', 'debug', 'dir', 'dirxml', 'error',
  'group', 'groupCollapsed', 'groupEnd', 'info', 'log', 'profile', 'profileEnd',
  'table', 'time', 'timeEnd', 'timeLog', 'trace', 'warn',
] as const

let initialized = false

function envBool(raw: string | undefined, fallback: boolean): boolean {
  if (raw === undefined || raw === '') return fallback
  return raw !== 'false' && raw !== '0'
}

function isAntiDebugEnabled(): boolean {
  const raw = import.meta.env.VITE_ANTI_DEBUG
  if (raw === undefined || raw === '') return import.meta.env.PROD
  return envBool(raw, import.meta.env.PROD)
}

function disableConsole(): void {
  const c = window.console as unknown as Record<string, (...args: unknown[]) => void>
  for (const method of CONSOLE_METHODS) {
    if (typeof c[method] === 'function') {
      try {
        c[method] = noop as (...args: unknown[]) => void
      } catch {
        /* ignore */
      }
    }
  }
  try {
    Object.freeze(window.console)
  } catch {
    /* ignore */
  }
}

function disableContextMenu(): void {
  document.addEventListener('contextmenu', (event) => event.preventDefault())
}

function disableDevtoolsShortcuts(): void {
  document.addEventListener(
    'keydown',
    (event: KeyboardEvent) => {
      const key = event.key.toUpperCase()
      const devtools = (event.ctrlKey || event.metaKey) && event.shiftKey && ['I', 'J', 'C'].includes(key)
      const viewSource = (event.ctrlKey || event.metaKey) && key === 'U'
      if (key === 'F12' || devtools || viewSource) {
        event.preventDefault()
        event.stopPropagation()
      }
    },
    true,
  )
}

function disableSelection(): void {
  const style = document.createElement('style')
  style.textContent =
    '*, *::before, *::after { -webkit-user-select: none !important; user-select: none !important; }'
  document.head.appendChild(style)
  document.addEventListener('selectstart', (event) => event.preventDefault())
  document.addEventListener('copy', (event) => event.preventDefault())
}

export function setupSecurity(): void {
  if (initialized) return
  initialized = true

  if (!isAntiDebugEnabled()) return

  if (envBool(import.meta.env.VITE_DISABLE_CONSOLE, true)) disableConsole()
  if (envBool(import.meta.env.VITE_DISABLE_CONTEXT_MENU, true)) disableContextMenu()
  if (envBool(import.meta.env.VITE_DISABLE_DEVTOOLS, true)) disableDevtoolsShortcuts()
  if (envBool(import.meta.env.VITE_DISABLE_SELECTION, false)) disableSelection()
}
