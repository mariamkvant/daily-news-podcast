import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mic, Mail } from 'lucide-react'
import api from '../api'
import { useAuthStore } from '../store'

export default function Register() {
  const navigate = useNavigate()
  const { setToken } = useAuthStore()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [registered, setRegistered] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError('Password must be at least 8 characters'); return }
    if (password.length > 72) { setError('Password must be 72 characters or fewer'); return }
    setLoading(true)
    try {
      const { data } = await api.post('/auth/register', { name, email, password })
      setToken(data.access_token)
      setRegistered(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  if (registered) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
        <div className="w-full max-w-md text-center">
          <div className="flex items-center justify-center gap-2 mb-8 text-2xl font-bold text-white">
            <Mic className="text-brand-500" size={28} />
            Daily News Podcast
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-10">
            <Mail className="text-brand-500 mx-auto mb-4" size={40} />
            <h2 className="text-white font-bold text-xl mb-3">Check your email</h2>
            <p className="text-gray-400 leading-relaxed">
              We sent a verification link to <span className="text-white font-medium">{email}</span>.
              Click it to activate your account and start listening.
            </p>
            <p className="text-gray-600 text-sm mt-6">
              Didn't get it?{' '}
              <button onClick={() => api.post(`/auth/resend-verification?email=${encodeURIComponent(email)}`)}
                className="text-brand-500 hover:text-brand-400">
                Resend
              </button>
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-8 text-2xl font-bold text-white">
          <Mic className="text-brand-500" size={28} />
          Daily News Podcast
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          <h2 className="text-2xl font-bold text-white mb-2">Create your account</h2>
          <p className="text-gray-400 text-sm mb-6">You'll pick your interests on the next step.</p>
          {error && <p className="text-red-400 text-sm mb-4 bg-red-400/10 px-4 py-2 rounded-lg">{error}</p>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Name</label>
              <input type="text" required value={name} onChange={e => setName(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 transition" />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 transition" />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Password</label>
              <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 transition" />
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white py-3 rounded-lg font-semibold transition mt-2">
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-500 hover:text-brand-400">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
