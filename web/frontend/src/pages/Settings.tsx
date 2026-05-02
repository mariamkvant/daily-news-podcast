import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Circle, Save } from 'lucide-react'
import api, { Catalog } from '../api'
import { useAuthStore } from '../store'
import clsx from 'clsx'

const DURATION_OPTIONS = [
  { label: '~1 min', value: 60 },
  { label: '~5 min', value: 300 },
  { label: '~10 min', value: 600 },
  { label: '~15 min', value: 900 },
  { label: '~30 min', value: 1800 },
  { label: '~60 min', value: 3600 },
]

export default function Settings() {
  const { user, setUser, logout } = useAuthStore()
  const navigate = useNavigate()
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [topics, setTopics] = useState<string[]>([])
  const [keywords, setKeywords] = useState<string[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [duration, setDuration] = useState(600)
  const [hour, setHour] = useState(7)
  const [minute, setMinute] = useState(0)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [tab, setTab] = useState<'topics' | 'keywords' | 'sources' | 'schedule'>('topics')

  useEffect(() => {
    api.get('/users/catalog').then(r => setCatalog(r.data))
    api.get('/users/me').then(r => {
      const u = r.data
      setUser(u)
      setTopics(u.topics || [])
      setKeywords(u.keywords || [])
      setSources(u.enabled_sources || [])
      setDuration(u.max_duration_sec || 600)
      setHour(u.generation_hour ?? 7)
      setMinute(u.generation_minute ?? 0)
    })
  }, [])

  function toggle<T>(arr: T[], val: T): T[] {
    return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]
  }

  async function save() {
    setSaving(true)
    try {
      const { data } = await api.put('/users/me/preferences', {
        topics, keywords, enabled_sources: sources,
        max_duration_sec: duration, generation_hour: hour, generation_minute: minute,
      })
      setUser(data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const tabs = ['topics', 'keywords', 'sources', 'schedule'] as const

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <Link to="/home" className="flex items-center gap-2 text-gray-400 hover:text-white transition">
          <ArrowLeft size={18} /> Back
        </Link>
        <h1 className="text-white font-semibold">Settings</h1>
        <button onClick={logout} className="text-gray-400 hover:text-red-400 text-sm transition">Sign out</button>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 mb-6">
          {tabs.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx('flex-1 py-2 rounded-lg text-sm font-medium capitalize transition',
                tab === t ? 'bg-brand-500 text-white' : 'text-gray-400 hover:text-white')}>
              {t}
            </button>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          {tab === 'topics' && catalog && (
            <>
              <h2 className="text-white font-semibold mb-4">Topics</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {catalog.topics.map(t => (
                  <button key={t} onClick={() => setTopics(toggle(topics, t))}
                    className={clsx('px-4 py-2.5 rounded-xl border text-sm font-medium capitalize transition',
                      topics.includes(t)
                        ? 'bg-brand-500/20 border-brand-500 text-brand-400'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500')}>
                    {t}
                  </button>
                ))}
              </div>
            </>
          )}

          {tab === 'keywords' && catalog && (
            <>
              <h2 className="text-white font-semibold mb-4">Keywords</h2>
              <div className="flex flex-wrap gap-2">
                {catalog.keywords.map(k => (
                  <button key={k} onClick={() => setKeywords(toggle(keywords, k))}
                    className={clsx('px-3 py-1.5 rounded-full border text-sm transition',
                      keywords.includes(k)
                        ? 'bg-brand-500/20 border-brand-500 text-brand-400'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500')}>
                    {k}
                  </button>
                ))}
              </div>
            </>
          )}

          {tab === 'sources' && catalog && (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-white font-semibold">Sources</h2>
                <div className="flex gap-2">
                  <button onClick={() => setSources(catalog.sources.map(s => s.name))}
                    className="text-xs text-gray-400 hover:text-white border border-gray-700 px-3 py-1 rounded-lg transition">All</button>
                  <button onClick={() => setSources([])}
                    className="text-xs text-gray-400 hover:text-white border border-gray-700 px-3 py-1 rounded-lg transition">None</button>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-96 overflow-y-auto">
                {catalog.sources.map(s => (
                  <button key={s.name} onClick={() => setSources(toggle(sources, s.name))}
                    className={clsx('flex items-center gap-3 px-4 py-3 rounded-xl border text-sm text-left transition',
                      sources.includes(s.name)
                        ? 'bg-brand-500/10 border-brand-500 text-white'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600')}>
                    {sources.includes(s.name)
                      ? <CheckCircle2 size={15} className="text-brand-500 shrink-0" />
                      : <Circle size={15} className="shrink-0" />}
                    {s.name}
                  </button>
                ))}
              </div>
            </>
          )}

          {tab === 'schedule' && (
            <>
              <h2 className="text-white font-semibold mb-6">Podcast Length</h2>
              <div className="grid grid-cols-3 gap-3 mb-8">
                {DURATION_OPTIONS.map(opt => (
                  <button key={opt.value} onClick={() => setDuration(opt.value)}
                    className={clsx('py-3 rounded-xl border text-sm font-medium transition',
                      duration === opt.value
                        ? 'bg-brand-500/20 border-brand-500 text-brand-400'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500')}>
                    {opt.label}
                  </button>
                ))}
              </div>
              <h2 className="text-white font-semibold mb-4">Daily Generation Time</h2>
              <div className="flex items-center gap-4">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Hour (0–23)</label>
                  <input type="number" min={0} max={23} value={hour} onChange={e => setHour(+e.target.value)}
                    className="w-20 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-center focus:outline-none focus:border-brand-500" />
                </div>
                <span className="text-gray-400 mt-4">:</span>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Minute (0–59)</label>
                  <input type="number" min={0} max={59} value={minute} onChange={e => setMinute(+e.target.value)}
                    className="w-20 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-center focus:outline-none focus:border-brand-500" />
                </div>
              </div>
            </>
          )}
        </div>

        <button onClick={save} disabled={saving}
          className="w-full mt-6 flex items-center justify-center gap-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition">
          {saved ? <><CheckCircle2 size={18} /> Saved!</> : saving ? 'Saving…' : <><Save size={18} /> Save changes</>}
        </button>
      </div>
    </div>
  )
}
