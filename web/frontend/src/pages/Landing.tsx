import { Link } from 'react-router-dom'
import { Mic, Rss, Zap, Globe } from 'lucide-react'

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-brand-900 to-gray-950 flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-2 text-xl font-bold text-white">
          <Mic className="text-brand-500" size={24} />
          Daily News Podcast
        </div>
        <div className="flex gap-4">
          <Link to="/login" className="text-gray-300 hover:text-white transition px-4 py-2">
            Sign in
          </Link>
          <Link to="/register"
            className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2 rounded-lg font-medium transition">
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center text-center px-6 py-20">
        <div className="inline-flex items-center gap-2 bg-brand-500/10 border border-brand-500/30 text-brand-500 text-sm px-4 py-1.5 rounded-full mb-8">
          <Zap size={14} /> Personalised news, delivered daily
        </div>
        <h1 className="text-5xl md:text-7xl font-extrabold text-white leading-tight max-w-4xl">
          Your world.<br />
          <span className="text-brand-500">Your podcast.</span>
        </h1>
        <p className="mt-6 text-xl text-gray-400 max-w-2xl">
          Pick your topics, choose your sources, set your length.
          We fetch the most important stories every day and turn them into
          a personalised audio podcast — ready when you are.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row gap-4">
          <Link to="/register"
            className="bg-brand-500 hover:bg-brand-600 text-white text-lg px-8 py-4 rounded-xl font-semibold transition shadow-lg shadow-brand-500/25">
            Create free account
          </Link>
          <Link to="/login"
            className="border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white text-lg px-8 py-4 rounded-xl font-semibold transition">
            Sign in
          </Link>
        </div>
      </main>

      {/* Features */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 px-8 pb-20 max-w-5xl mx-auto w-full">
        {[
          { icon: Globe, title: '50+ World Sources', desc: 'BBC, Reuters, AP, NYT, FT, Al Jazeera and more — all in one place.' },
          { icon: Zap, title: 'Importance Scoring', desc: 'Multi-signal ranking picks the most critical stories, not just the most recent.' },
          { icon: Rss, title: 'Your Interests', desc: 'Choose topics like Tech, Climate, Finance. Add keywords. Exclude sources you don\'t trust.' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6">
            <Icon className="text-brand-500 mb-3" size={28} />
            <h3 className="text-white font-semibold text-lg mb-2">{title}</h3>
            <p className="text-gray-400 text-sm">{desc}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
