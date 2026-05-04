import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Play, Pause, SkipForward, RotateCcw, RefreshCw, Settings, Mic, LogOut, SlidersHorizontal } from 'lucide-react'
import api, { Episode, Segment } from '../api'
import { useAuthStore } from '../store'
import clsx from 'clsx'

function fmt(ms: number) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function Home() {
  const { user, setUser, logout } = useAuthStore()
  const [episode, setEpisode] = useState<Episode | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [currentIdx, setCurrentIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [speed, setSpeed] = useState(1)
  const audioRef = useRef<HTMLAudioElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load user profile
  useEffect(() => {
    api.get('/users/me').then(r => setUser(r.data))
  }, [])

  // Load today's episode
  const loadEpisode = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get<Episode>('/episodes/today')
      setEpisode(data)
      if (data.status === 'pending' || data.status === 'generating') {
        setGenerating(true)
        startPolling()
      } else {
        setGenerating(false)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadEpisode() }, [loadEpisode])

  function startPolling() {
    if (pollRef.current) return
    const startTime = Date.now()
    pollRef.current = setInterval(async () => {
      const { data } = await api.get<Episode>('/episodes/today')
      setEpisode(data)
      if (data.status === 'ready' || data.status === 'failed') {
        setGenerating(false)
        clearInterval(pollRef.current!)
        pollRef.current = null
      }
      // Auto-cancel if stuck generating for more than 3 minutes
      if (data.status === 'generating' && Date.now() - startTime > 180000) {
        try { await api.post('/episodes/cancel') } catch {}
        setGenerating(false)
        clearInterval(pollRef.current!)
        pollRef.current = null
        loadEpisode()
      }
    }, 4000)
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  // Audio events
  const seg: Segment | undefined = episode?.segments[currentIdx]

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !seg) return
    audio.src = seg.audio_url
    audio.playbackRate = speed
    if (playing) audio.play().catch(() => {})
  }, [currentIdx, seg?.audio_url])

  function togglePlay() {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
    } else {
      audio.play()
        .then(() => setPlaying(true))
        .catch(e => console.error('Play failed:', e))
    }
  }

  function changeSpeed(s: number) {
    setSpeed(s)
    if (audioRef.current) audioRef.current.playbackRate = s
  }

  function skip() {
    if (!episode) return
    const next = currentIdx + 1
    if (next < episode.segments.length) {
      setCurrentIdx(next)
      setElapsed(0)
      // Auto-play next segment
      setTimeout(() => {
        const audio = audioRef.current
        if (audio) audio.play().then(() => setPlaying(true)).catch(() => {})
      }, 100)
    } else {
      setPlaying(false)
    }
  }

  function replay() {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = 0
    audio.play().then(() => setPlaying(true)).catch(() => {})
  }

  function jumpTo(idx: number) {
    setCurrentIdx(idx)
    setElapsed(0)
    setTimeout(() => {
      const audio = audioRef.current
      if (audio) audio.play().then(() => setPlaying(true)).catch(() => {})
    }, 100)
  }

  async function generateNow() {
    setGenerating(true)
    await api.post('/episodes/generate')
    startPolling()
  }

  const totalElapsed = (episode?.segments.slice(0, currentIdx).reduce((a, s) => a + s.duration_ms, 0) ?? 0) + elapsed

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2 font-bold text-white">
          <Mic className="text-brand-500" size={20} />
          Daily News Podcast
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm hidden sm:block">Hi, {user?.name}</span>
          <Link to="/settings"
            className="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white px-3 py-1.5 rounded-lg text-sm font-medium transition">
            <SlidersHorizontal size={14} />
            <span>Customise</span>
          </Link>
          <button onClick={logout} className="text-gray-400 hover:text-white transition p-1.5 rounded-lg hover:bg-gray-800">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <main className="flex-1 flex flex-col lg:flex-row gap-0 max-w-6xl mx-auto w-full p-6 gap-6">
        {/* Player */}
        <div className="lg:w-96 shrink-0">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 sticky top-6">
            {loading ? (
              <div className="text-center text-gray-500 py-12">Loading episode…</div>
            ) : generating ? (
              <div className="text-center py-12">
                <RefreshCw className="animate-spin text-brand-500 mx-auto mb-4" size={32} />
                <p className="text-white font-medium">Generating your episode…</p>
                <p className="text-gray-400 text-sm mt-2">Fetching and converting stories</p>
                <button onClick={async () => {
                  try { await api.post('/episodes/cancel') } catch {}
                  setGenerating(false)
                  if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
                  await loadEpisode()
                }} className="mt-6 text-xs text-gray-600 hover:text-gray-400 transition underline">
                  Taking too long? Cancel
                </button>
              </div>
            ) : episode?.status === 'failed' ? (
              <div className="text-center py-12">
                <p className="text-red-400 font-medium mb-4">Generation failed</p>
                <button onClick={generateNow}
                  className="bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-lg font-medium transition">
                  Try again
                </button>
              </div>
            ) : episode ? (
              <>
                {/* Date + summary */}
                <div className="mb-6">
                  <p className="text-brand-500 text-sm font-medium mb-1">
                    {new Date(episode.date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                  </p>
                  <h2 className="text-white font-bold text-lg leading-snug">
                    {episode.segments.length} stories · {fmt(episode.total_duration_ms)}
                  </h2>
                  {episode.summary && (
                    <p className="text-gray-400 text-sm mt-2 leading-relaxed">{episode.summary}</p>
                  )}
                </div>

                {/* Now playing */}
                {seg && (
                  <div className="bg-gray-800 rounded-xl p-4 mb-5">
                    <p className="text-xs text-brand-500 font-medium mb-1">NOW PLAYING</p>
                    <p className="text-white font-semibold text-sm leading-snug">{seg.title}</p>
                    <p className="text-gray-400 text-xs mt-1">{seg.source_name}</p>
                  </div>
                )}

                {/* Progress */}
                <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                  <span>{fmt(totalElapsed)}</span>
                  <span>{fmt(episode.total_duration_ms)}</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-1.5 mb-5">
                  <div className="bg-brand-500 h-1.5 rounded-full transition-all"
                    style={{ width: `${Math.min(100, (totalElapsed / episode.total_duration_ms) * 100)}%` }} />
                </div>

                {/* Controls */}
                <div className="flex items-center justify-center gap-4">
                  <button onClick={replay} className="text-gray-400 hover:text-white transition p-2">
                    <RotateCcw size={20} />
                  </button>
                  <button onClick={togglePlay}
                    className="bg-brand-500 hover:bg-brand-600 text-white rounded-full p-4 transition shadow-lg shadow-brand-500/30">
                    {playing ? <Pause size={24} /> : <Play size={24} />}
                  </button>
                  <button onClick={skip} className="text-gray-400 hover:text-white transition p-2">
                    <SkipForward size={20} />
                  </button>
                </div>

                {/* Speed control */}
                <div className="flex items-center justify-center gap-1 mt-4">
                  {[0.75, 1, 1.25, 1.5, 2].map(s => (
                    <button key={s} onClick={() => changeSpeed(s)}
                      className={clsx(
                        'px-2.5 py-1 rounded-lg text-xs font-medium transition',
                        speed === s
                          ? 'bg-brand-500 text-white'
                          : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
                      )}>
                      {s}x
                    </button>
                  ))}
                </div>

                <button onClick={generateNow} disabled={generating}
                  className="w-full mt-5 flex items-center justify-center gap-2 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg py-2.5 transition disabled:opacity-40">
                  <RefreshCw size={14} /> Regenerate
                </button>
              </>
            ) : null}
          </div>
        </div>

        {/* Story list */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-semibold text-lg">Today's Stories</h3>
            <Link to="/settings"
              className="flex items-center gap-1.5 text-sm text-brand-500 hover:text-brand-400 transition">
              <SlidersHorizontal size={14} />
              Customise feed
            </Link>
          </div>
          {episode?.segments.map((s, i) => (
            <button key={s.id} onClick={() => jumpTo(i)}
              className={clsx(
                'w-full text-left bg-gray-900 border rounded-xl p-5 mb-3 transition',
                i === currentIdx && playing
                  ? 'border-brand-500 bg-brand-500/5'
                  : 'border-gray-800 hover:border-gray-600'
              )}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-500 font-medium">#{i + 1}</span>
                    <span className="text-xs text-brand-500 font-medium">{s.source_name}</span>
                    <span className="text-xs text-gray-600">{fmt(s.duration_ms)}</span>
                  </div>
                  <p className="text-white font-semibold text-sm leading-snug">{s.title}</p>
                  {s.summary && (
                    <p className="text-gray-400 text-xs mt-2 leading-relaxed line-clamp-3">{s.summary}</p>
                  )}
                </div>
                {i === currentIdx && playing && (
                  <div className="flex gap-0.5 items-end h-5 shrink-0 mt-1">
                    {[1, 2, 3].map(b => (
                      <div key={b} className="w-1 bg-brand-500 rounded-full animate-pulse"
                        style={{ height: `${40 + b * 20}%`, animationDelay: `${b * 0.15}s` }} />
                    ))}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      </main>

      {/* Hidden audio element */}
      <audio ref={audioRef}
        onTimeUpdate={() => setElapsed(Math.floor((audioRef.current?.currentTime ?? 0) * 1000))}
        onEnded={skip}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
    </div>
  )
}
