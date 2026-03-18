import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import SearchBar from './SearchBar'
import DataFreshnessBanner from './DataFreshnessBanner'

const NAV = [
  { path: '/', label: 'Discover' },
  { path: '/emerging', label: 'Emerging' },
  { path: '/narratives', label: 'Narratives' },
  { path: '/screener', label: 'Screener' },
  { path: '/taxonomy', label: 'Taxonomy' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation()

  return (
    <div className="min-h-screen bg-surface">
      <DataFreshnessBanner />
      <header className="bg-card border-b border-border sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-6">
              <Link to="/">
                <img src="/logo.png" alt="Duodecimal" className="h-8" />
              </Link>
              <nav className="flex gap-1">
                {NAV.map(({ path, label }) => (
                  <Link
                    key={path}
                    to={path}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      loc.pathname === path
                        ? 'bg-card-hover text-text-primary'
                        : 'text-text-muted hover:text-text-primary hover:bg-card-hover'
                    }`}
                  >
                    {label}
                  </Link>
                ))}
              </nav>
            </div>
            <SearchBar />
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>
    </div>
  )
}
