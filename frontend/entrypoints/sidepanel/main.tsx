import React from 'react';
import { createRoot } from 'react-dom/client';
import { AppLayout } from '../../components/AppLayout';
import { AutoFillReviewScreen } from '../../pages/AutoFillReviewScreen';
import '../popup/style.css';
import './style.css';

function SidePanel() {
  return (
    <AppLayout defaultTheme="dark" surface="sidepanel">
      <AutoFillReviewScreen />
      <p className="step-label">Auto-fill review · 6 of 6</p>
    </AppLayout>
  );
}

const root = document.getElementById('root');

if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <SidePanel />
    </React.StrictMode>,
  );
}
