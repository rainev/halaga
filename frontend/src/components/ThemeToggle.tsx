import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { cn } from '@/lib/utils'

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme()
  const dark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        'grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] text-[var(--app-text)] shadow-sm hover:-translate-y-0.5 hover:shadow-md',
        className,
      )}
      aria-label={`Switch to ${dark ? 'light' : 'dark'} mode`}
      title={`Switch to ${dark ? 'light' : 'dark'} mode`}
    >
      <span className="relative grid h-5 w-5 place-items-center overflow-hidden">
        <Sun className={cn('absolute h-5 w-5 transition-all duration-300', dark ? '-rotate-90 scale-0 opacity-0' : 'rotate-0 scale-100 opacity-100')} />
        <Moon className={cn('absolute h-5 w-5 transition-all duration-300', dark ? 'rotate-0 scale-100 opacity-100' : 'rotate-90 scale-0 opacity-0')} />
      </span>
    </button>
  )
}
