import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Circle } from 'lucide-react'
import api, { Catalog } from '../api'
import clsx from 'clsx'

const DURATION_OPTIONS = [
  { label: '~1 min', sub: 'Quick headlines', value: 60 },
  { label: '~5 min', sub: 'Brief overview', value: 300 },
  { label: '~10 min', sub: 'Standard', value: 600 },
  { label: '~15 min', sub: 'Extended', value: 900 },
  { label: '~30 min', sub: 'Deep dive', value: 1800 },
  { label: '~60 min', sub: 'Full edition', value: 3600 },
]

export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [topics, setTopics] = useState<string[]>(['world', 'technology', 'business', 'science'])
  const [keywords, setKeywords] = useState<string[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [duration, setDuration] = useState(600)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/users/catalog').then(r => {
      setCatalog(r.data)
      setSources(r.data.sources.slice(0, 6).map((s: any) => s.name))
    })
  }, [])

  function toggle<T>(arr: T[], val: T): T[] {
    return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]
  }

  async function finish() {
    setSaving(true)
    await api.put('/users/me/preferences', {
      topics, keywords, enabled_sources: sources,
      max_duration_sec: duration, generation_hour: 7, generation_minute: 0,
    })
    navigate('/home')
  }

  if (!catalog) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="text-gray-400">Loading…</div>
    </div>
  )

  const steps = ['Topics', 'Keywords', 'Sources', 'Length']

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-10">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <button onClick={() => i < step && setStep(i)}
                className={clsx('flex items-center gap-1.5 text-sm font-medium transition',
                  i === step ? 'text-brand-500' : i < step ? 'text-green-400' : 'text-gray-600')}>
                {i < step ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                {s}
              </button>
              {i < steps.length - 1 && <div className="w-8 h-px bg-gray-800" />}
            </div>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          {/* Step 0: Topics */}
          {step === 0 && (
            <>
              <h2 className="text-2xl font-bold text-white mb-2">What topics interest you?</h2>
              <p className="text-gray-400 text-sm mb-6">Pick at least one. You can change this later.</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {catalog.topics.map(t => (
                  <button key={t} onClick={() => setTopics(toggle(topics, t))}
                    className={clsx('px-4 py-3 rounded-xl border text-sm font-medium transition capitalize',
                      topics.includes(t)
                        ? 'bg-brand-500/20 border-brand-500 text-brand-400'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500')}>
                    {t}
                  </button>
                ))}
              </div>
            </>
          )}

          {/* Step 1: Keywords */}
          {step === 1 && (
            <>
              <h2 className="text-2xl font-bold text-white mb-2">Any specific keywords?</h2>
              <p className="text-gray-400 text-sm mb-6">These boost stories that mention these terms. Optional.</p>
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

          {/* Step 2: Sources */}
          {step === 2 && (
            <>
              <h2 className="text-2xl font-bold text-white mb-2">Choose your news sources</h2>
              <p className="text-gray-400 text-sm mb-6">Enable the outlets you trust.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-80 overflow-y-auto pr-1">
                {catalog.sources.map(s => (
                  <button key={s.name} onClick={() => setSources(toggle(sources, s.name))}
                    className={clsx('flex items-center gap-3 px-4 py-3 rounded-xl border text-sm text-left transition',
                      sources.includes(s.name)
                        ? 'bg-brand-500/10 border-brand-500 text-white'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600')}>
                    {sources.includes(s.name)
                      ? <CheckCircle2 size={16} className="text-brand-500 shrink-0" />
                      : <Circle size={16} className="shrink-0" />}
                    <span className="font-medium">{s.name}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* Step 3: Duration */}
          {step === 3 && (
            <>
              <h2 className="text-2xl font-bold text-white mb-2">How long should your podcast be?</h2>
              <p className="text-gray-400 text-sm mb-6">You can change this any time in settings.</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {DURATION_OPTIONS.map(opt => (
                  <button key={opt.value} onClick={() => setDuration(opt.value)}
                    className={clsx('px-4 py-4 rounded-xl border text-left transition',
                      duration === opt.value
                        ? 'bg-brand-500/20 border-brand-500'
                        : 'bg-gray-800 border-gray-700 hover:border-gray-500')}>
                    <div className={clsx('font-bold text-lg', duration === opt.value ? 'text-brand-400' : 'text-white')}>
                      {opt.label}
                    </div>
                    <div className="text-gray-400 text-xs mt-0.5">{opt.sub}</div>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* Navigation */}
          <div className="flex justify-between mt-8">
            <button onClick={() => setStep(s => s - 1)} disabled={step === 0}
              className="px-6 py-2.5 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500 disabled:opacity-30 transition">
              Back
            </button>
            {step < steps.length - 1 ? (
              <button onClick={() => setStep(s => s + 1)} disabled={step === 0 && topics.length === 0}
                className="px-6 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-medium disabled:opacity-50 transition">
                Next
              </button>
            ) : (
              <button onClick={finish} disabled={saving}
                className="px-6 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-medium disabled:opacity-50 transition">
                {saving ? 'Saving…' : 'Start listening →'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
