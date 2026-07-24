import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// Minimal typing for the slice of Google Identity Services we use, so we don't
// need @types/google.accounts just for this.
interface CredentialResponse {
  credential?: string
}
interface GoogleAccountsId {
  initialize: (config: {
    client_id: string
    callback: (res: CredentialResponse) => void
  }) => void
  renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void
}
declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } }
  }
}

const GIS_SRC = 'https://accounts.google.com/gsi/client'
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

// Loads the GIS script once and caches the promise so multiple buttons (Login +
// Register) don't each inject a <script>.
let gisPromise: Promise<void> | null = null
function loadGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve()
  if (gisPromise) return gisPromise
  gisPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Google sign-in.'))
    document.head.appendChild(script)
  })
  return gisPromise
}

/**
 * "Sign in with Google" button. Renders nothing when VITE_GOOGLE_CLIENT_ID is
 * unset, so the app works fine without Google configured.
 */
export function GoogleSignInButton({ onError }: { onError?: (message: string) => void }) {
  const { googleLogin } = useAuth()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    if (!CLIENT_ID) {
      setUnavailable(true)
      return
    }
    let cancelled = false

    loadGis()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: async (res) => {
            if (!res.credential) return
            try {
              await googleLogin(res.credential)
              navigate('/')
            } catch (err) {
              onError?.(err instanceof Error ? err.message : 'Google sign-in failed.')
            }
          },
        })
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'continue_with',
        })
      })
      .catch(() => {
        if (!cancelled) setUnavailable(true)
      })

    return () => {
      cancelled = true
    }
  }, [googleLogin, navigate, onError])

  if (unavailable) return null
  // GIS injects its own button markup into this container.
  return <div ref={containerRef} className="flex justify-center" />
}
