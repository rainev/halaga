import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeState | null>(null)

function initialTheme(): Theme {
  const saved = localStorage.getItem('finsight-theme')
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.style.colorScheme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      'content',
      theme === 'dark' ? '#121212' : '#fafafa',
    )
    localStorage.setItem('finsight-theme', theme)
  }, [theme])

  const value = useMemo<ThemeState>(() => ({
    theme,
    toggleTheme: () => setTheme((current) => current === 'light' ? 'dark' : 'light'),
  }), [theme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme must be used inside ThemeProvider')
  return value
}
