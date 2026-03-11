import { NavLink, Route, Routes } from 'react-router-dom'
import { GalleryPage } from './pages/GalleryPage'
import { MetricsPage } from './pages/MetricsPage'
import { StudioPage } from './pages/StudioPage'

export function App() {
  return (
    <div className="app-root">
      <header className="topbar">
        <div className="brand">电商生图 MVP</div>
        <nav className="nav">
          <NavLink to="/studio" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            生成工作台
          </NavLink>
          <NavLink to="/gallery" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            历史画廊
          </NavLink>
          <NavLink to="/metrics" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            统计看板
          </NavLink>
        </nav>
      </header>

      <main className="page-wrap">
        <Routes>
          <Route path="/" element={<StudioPage />} />
          <Route path="/studio" element={<StudioPage />} />
          <Route path="/gallery" element={<GalleryPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
        </Routes>
      </main>
    </div>
  )
}
