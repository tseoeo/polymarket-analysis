import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/layout';
import {
  Dashboard,
  AlertsPage,
  AlertDetailPage,
  MarketsPage,
  MarketDetailPage,
  ArbitragePage,
  OrderBookPage,
  VolumePage,
  MarketMakerPage,
} from '@/pages';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="alerts/:id" element={<AlertDetailPage />} />
          <Route path="markets" element={<MarketsPage />} />
          <Route path="markets/:id" element={<MarketDetailPage />} />
          <Route path="arbitrage" element={<ArbitragePage />} />
          <Route path="orderbook" element={<OrderBookPage />} />
          <Route path="volume" element={<VolumePage />} />
          <Route path="mm" element={<MarketMakerPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
