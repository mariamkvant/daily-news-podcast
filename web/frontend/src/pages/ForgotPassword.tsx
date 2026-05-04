import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Mic, Mail, ArrowLeft } from 'lucide-react'
import api from '../api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await api.post(`/auth/forgot-password?email=${encodeURIComponent(email)}`)
      setSent(true)
    } catch {
      setError('Something went wrong. Please try again.')
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
          {sent ? (
            <div className="text-center">
              <Mail className="text-brand-500 mx-auto mb-4" size={40} />
              <h2 className="text-white font-bold text-xl mb-3">Check your email</h2>
              <p className="text-gray-400">If that email exists, we've sent a reset link. Check your inbox.</p>
              <Link to="/login" className="inline-block mt-6 text-brand-500 hover:text-brand-400">
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <Link to="/login" className="flex items-center gap-1 text-gray-400 hover:text-white text-sm mb-6 transition">
                <ArrowLeft size={14} /> Back to sign in
              </Link>
              <h2 className="text-2xl font-bold text-white mb-2">Forgot password?</h2>
              <p className="text-gray-400 text-sm mb-6">Enter your email and we'll send you a reset link.</p>
              {error && <p className="text-red-400 text-sm mb-4 bg-red-400/10 px-4 py-2 rounded-lg">{error}</p>}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Email</label>
                  <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 transition" />
                </div>
                <button type="submit" disabled={loading}
                  className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white py-3 rounded-lg font-semibold transition">
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
