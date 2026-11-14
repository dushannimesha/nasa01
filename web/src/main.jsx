import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import Simple from "./pages/Simple.jsx";
import DataPage from "./pages/Data.jsx";
import { useLang } from "./lib/i18n.jsx";
import "./styles.css";
import "./simple.css";
import Gov from "./pages/Gov.jsx";
// The 2021 evaluation report is a separate page with its own link (/2021), loaded only when asked for.
const Backtest = React.lazy(() => import("./pages/Backtest.jsx"));
import Farmer from "./pages/Farmer.jsx";
import Officer from "./pages/Officer.jsx";
import Outlook from "./pages/Outlook.jsx";

function Online() {
  const [on, setOn] = React.useState(navigator.onLine);
  React.useEffect(() => {
    const up = () => setOn(true), down = () => setOn(false);
    window.addEventListener("online", up); window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  const { t } = useLang();
  const farmerSide = useLocation().pathname.startsWith("/farm");
  return on ? null : <span className="chip warn">{farmerSide ? t.offline : "Offline: using saved data"}</span>;
}

function Footer() {
  const { t } = useLang();
  const farmerSide = useLocation().pathname === "/farm";
  return (
    <footer className="foot">
      {farmerSide ? t.disclaimer : "Decision support only. It does not replace farmer judgment or the advice of agricultural officers."}{" "}
      Data: NASA POWER, GPM IMERG, MODIS, SMAP, SRTM, SoilGrids, Open-Meteo, DCS, HARTI (<a href="/data">details</a>). Boundaries: geoBoundaries (ODbL), Natural Earth.
    </footer>
  );
}

// Farmers get their own link (/farm) with no government menu; the detailed farmer page keeps that plain header too.
function Header() {
  const { pathname } = useLocation();
  const farmerSide = pathname.startsWith("/farm");
  const { t } = useLang();
  if (pathname === "/2021") return (
    <header className="top">
      <div className="brand"><img src="/icon.svg" alt="" width="28" height="28" /><div><b>Field Shift</b><small>Evaluation report · crop year 2021</small></div></div>
      <nav><a href="/">Open the app <ExternalLink size={14} aria-hidden="true" /></a></nav>
    </header>
  );
  return (
    <header className="top">
      <div className="brand"><img src="/icon.svg" alt="" width="28" height="28" /><div><b>Field Shift</b><small>{farmerSide ? (pathname === "/farm" ? t.tagline : "Crop advice for your field") : "Sri Lanka · crop year 2021"}</small></div></div>
      {farmerSide ? (
        <nav>
          <NavLink to="/farm" end>Simple</NavLink>
          <NavLink to="/farmer">Detailed</NavLink>
        </nav>
      ) : (
        <nav>
          <NavLink to="/" end>National dashboard</NavLink>
          <NavLink to="/officer">Officer</NavLink>
          <NavLink to="/outlook">Harvest outlook</NavLink>
          <NavLink to="/data">Data used</NavLink>
          <NavLink to="/farm">Farmer app <ExternalLink size={14} aria-hidden="true" /></NavLink>
        </nav>
      )}
      <Online />
    </header>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Header />
      <main>
        <Routes>
          <Route path="/farm" element={<Simple />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/" element={<Gov />} />
          <Route path="/2021" element={<React.Suspense fallback={<div className="loading">Loading the report…</div>}><Backtest /></React.Suspense>} />
          <Route path="/backtest" element={<Navigate to="/2021" replace />} />
          <Route path="/farmer" element={<Farmer />} />
          <Route path="/officer" element={<Officer />} />
          <Route path="/outlook" element={<Outlook />} />
        </Routes>
      </main>
      <Footer />
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<App />);
