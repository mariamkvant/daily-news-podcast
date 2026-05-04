import React from 'react'

interface State { hasError: boolean; error: string }

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false, error: '' }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
          <div className="text-center max-w-md">
            <p className="text-4xl mb-4">⚠️</p>
            <h2 className="text-white font-bold text-xl mb-2">Something went wrong</h2>
            <p className="text-gray-400 text-sm mb-6">{this.state.error}</p>
            <button onClick={() => window.location.reload()}
              className="bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-lg font-medium transition">
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
