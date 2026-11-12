import { useEffect, useState } from 'react';
import { browser } from 'wxt/browser';
import { PDFDocument } from 'pdf-lib';
import type { Resume } from '../../types';
import { downloadResume, getResumeFile } from '../../services/resumeFiles';
import { Button } from '../../components/Button';

export async function openResumePreview(resume: Resume) {
  const url = new URL(browser.runtime.getURL('/resume-preview.html'));
  url.searchParams.set('id', resume.id);
  url.searchParams.set('name', resume.name);
  await browser.tabs.create({ url: url.href });
}

export function ResumeFileActions({ resume, showPreview = true }: { resume: Resume; showPreview?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function download() {
    setBusy(true);
    setMessage('');
    try {
      await downloadResume(resume.id, resume.name);
      setMessage('Download started.');
    } catch { setMessage('Download failed. Please try again.'); }
    finally { setBusy(false); }
  }
  return (
    <div className="resume-file-actions">
      {showPreview && <Button variant="secondary" onClick={() => void openResumePreview(resume).catch(() => setMessage('Could not open preview. Please try again.'))}>Preview</Button>}
      <Button onClick={() => void download()} disabled={busy}>{busy ? 'Preparing…' : 'Download'}</Button>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

export function ResumePreviewDownload() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get('id') ?? '';
  const name = params.get('name') || 'Resume';
  const fileName = name.toLowerCase().endsWith('.pdf') ? name : `${name}.pdf`;
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ url?: string; error?: string }>({});
  const [viewerReady, setViewerReady] = useState(false);

  useEffect(() => {
    document.title = fileName;
    const controller = new AbortController();
    let active = true;
    let objectUrl: string | undefined;
    setState({});
    setViewerReady(false);
    getResumeFile(id, controller.signal).then(async (file) => {
      if (!active) return;
      if (file.type !== 'application/pdf') throw new Error('Preview is unavailable for this document. You can still try downloading it.');
      // Chrome's PDF toolbar reads embedded document titles, including stale
      // source HTML names. Normalize only this in-memory preview copy.
      let previewFile = file;
      try {
        const pdf = await PDFDocument.load(await file.arrayBuffer());
        pdf.setTitle(fileName);
        const bytes = await pdf.save();
        previewFile = new Blob([new Uint8Array(bytes)], { type: 'application/pdf' });
      } catch {
        // Encrypted or otherwise uneditable PDFs may still render natively.
      }
      if (!active) return;
      objectUrl = URL.createObjectURL(previewFile);
      setState({ url: objectUrl });
    }).catch((error: unknown) => {
      if (active) setState({ error: error instanceof Error ? error.message : 'Could not load this resume.' });
    });
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id, attempt, fileName]);

  return (
    <main className="resume-preview-page">
      <section className="preview-document" aria-label="Resume document" aria-busy={!state.error && !viewerReady}>
        {state.error ? <div className="preview-feedback" role="alert"><h2>Preview unavailable</h2><p>{state.error}</p><Button onClick={() => setAttempt(attempt + 1)}>Retry preview</Button></div> : <>
          {!viewerReady && <div className="preview-feedback" role="status">Loading preview…</div>}
          {state.url && <iframe title={`PDF preview of ${name}`} src={`${state.url}#view=FitH`} onLoad={() => setViewerReady(true)} onError={() => setState({ error: 'The document viewer could not load. Download the file from the resume menu in the Vault instead.' })} />}
        </>}
      </section>
      <p className="preview-help">PDF not displaying? Download the file from the resume’s ⋯ menu in the Vault.</p>
    </main>
  );
}
