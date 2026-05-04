import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Mic, CheckCircle2 } from 'lucide-react'
import api from '../api'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) { setError('Passwords do not match'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return }
    setLoading(true)
    setError('')
    try {
      const token = params.get('token') || ''
      await api.post(`/auth/reset-password?token=${encodeURIComponent(token)}&new_password=${encodeURIComponent(password)}`)
      setDone(true)
      setTimeout(() => navigate('/login'), 2000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Reset failed. The link may have expired.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-8 text-2xl font-bold text-white">
          <Mic className="text-brand-500" size={28} />
          Daily News Podcast
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          {done ? (
            <div className="text-center">
              <CheckCircle2 className="text-green-400 mx-auto mb-4" size={40} />
              <h2 className="text-white font-bold text-xl mb-2">Password reset!</h2>
              <p className="text-gray-400 text-sm">Taking you to sign in…</p>
            </div>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-white mb-2">Set new password</h2>
              <p className="text-gray-400 text-sm mb-6">Choose a strong password for your account.</p>
              {error && <p className="text-red-400 text-sm mb-4 bg-red-400/10 px-4 py-2 rounded-lg">{error}</p>}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">New password</label>
                  <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 transition" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Confirm password</label>
                  <input type="password" required value={confirm} onChange={e => setConfirm(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 transition" />
                </div>
                <button type="submit" disabled={loading}
                  className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white py-3 rounded-lg font-semibold transition">
                  {loading ? 'Resetting…' : 'Reset password'}
                </button>
              </form>
              <p className="text-center text-gray-600 text-sm mt-4">
                <Link to="/login" className="text-brand-500 hover:text-brand-400">Back to sign in</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
