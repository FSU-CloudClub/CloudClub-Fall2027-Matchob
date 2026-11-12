import React from 'react';
import { createRoot } from 'react-dom/client';
import { ResumePreviewDownload } from '../../features/resumes/ResumePreviewDownload';
import '../popup/style.css';
import '../../features/resumes/ResumeVault.css';
import './style.css';

createRoot(document.getElementById('root')!).render(<React.StrictMode><ResumePreviewDownload /></React.StrictMode>);
