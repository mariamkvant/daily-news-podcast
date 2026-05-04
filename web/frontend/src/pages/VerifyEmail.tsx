import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2, Mic } from 'lucide-react'
import api from '../api'
import { useAuthStore } from '../store'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { setToken } = useAuthStore()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    const token = params.get('token')
    if (!token) {
      setStatus('error')
      setError('No verification token found.')
      return
    }
    api.get(`/auth/verify?token=${token}`)
      .then(r => {
        setToken(r.data.access_token)
        setStatus('success')
        setTimeout(() => navigate('/onboarding'), 2000)
      })
      .catch(err => {
        setStatus('error')
        setError(err.response?.data?.detail || 'Verification failed.')
      })
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md text-center">
        <div className="flex items-center justify-center gap-2 mb-8 text-2xl font-bold text-white">
          <Mic className="text-brand-500" size={28} />
          Daily News Podcast
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-10">
          {status === 'loading' && (
            <>
              <Loader2 className="animate-spin text-brand-500 mx-auto mb-4" size={40} />
              <p className="text-white font-semibold text-lg">Verifying your email…</p>
            </>
          )}
          {status === 'success' && (
            <>
              <CheckCircle2 className="text-green-400 mx-auto mb-4" size={40} />
              <p className="text-white font-semibold text-lg">Email verified!</p>
              <p className="text-gray-400 text-sm mt-2">Taking you to set up your interests…</p>
            </>
          )}
          {status === 'error' && (
            <>
              <XCircle className="text-red-400 mx-auto mb-4" size={40} />
              <p className="text-white font-semibold text-lg">Verification failed</p>
              <p className="text-red-400 text-sm mt-2">{error}</p>
              <Link to="/register"
                className="inline-block mt-6 bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-lg font-medium transition">
                Back to register
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
