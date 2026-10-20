import React from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeToggle } from '../../components/ThemeToggle';
import { AutoFillReviewScreen } from '../../pages/AutoFillReviewScreen';
import '../popup/style.css';
import './style.css';

function SidePanel() {
  return (
    <main className="popup sidepanel">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <span>Matchob</span>
        <ThemeToggle defaultTheme="dark" />
      </header>
      <AutoFillReviewScreen />
      <p className="step-label">Auto-fill review · 6 of 6</p>
    </main>
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
