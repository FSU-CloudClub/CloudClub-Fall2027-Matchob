import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './style.css';

// WXT turns this folder's index.html into the browser-action popup.
const root = document.getElementById('root');

if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
