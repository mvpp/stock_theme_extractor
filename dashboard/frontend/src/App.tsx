import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DiscoverPage from './pages/DiscoverPage'
import ThemeDetailPage from './pages/ThemeDetailPage'
import StockDetailPage from './pages/StockDetailPage'
import EmergingPage from './pages/EmergingPage'
import NarrativesPage from './pages/NarrativesPage'
import ScreenerPage from './pages/ScreenerPage'
import PromotionPage from './pages/PromotionPage'
import TaxonomyPage from './pages/TaxonomyPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DiscoverPage />} />
        <Route path="/themes/:name" element={<ThemeDetailPage />} />
        <Route path="/stocks/:ticker" element={<StockDetailPage />} />
        <Route path="/emerging" element={<EmergingPage />} />
        <Route path="/narratives" element={<NarrativesPage />} />
        <Route path="/screener" element={<ScreenerPage />} />
        <Route path="/promotions" element={<PromotionPage />} />
        <Route path="/taxonomy" element={<TaxonomyPage />} />
        <Route path="/search" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
