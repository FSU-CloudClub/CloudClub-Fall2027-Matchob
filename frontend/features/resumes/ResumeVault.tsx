import { useEffect, useState } from 'react';
import { browser } from 'wxt/browser';
import { resumeApi } from '../../services/resumeApi';
import type { Resume } from '../../types';
import pdfIcon from '../../assets/icons/file-earmark-pdf.svg';
import { ResumeUpload } from './ResumeUpload';
import './ResumeVault.css';

const uploadDate = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

export function ResumeVault() {
  const [openActions, setOpenActions] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [visibleResumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Resume | null>(null);
  const [name, setName] = useState('');
  const [tags, setTags] = useState('');
  const [deleting, setDeleting] = useState<Resume | null>(null);

  async function refresh() {
    setLoading(true);
    try { setResumes(await resumeApi.getResumes()); setNotice(''); }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load resumes.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);

  async function perform(action: () => Promise<void>) {
    setBusy(true); setNotice(''); setOpenActions(null);
    try { await action(); }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Request failed.'); }
    finally { setBusy(false); }
  }

  function preview(resume: Resume) {
    void perform(async () => {
      const url = await resumeApi.getDownloadUrl(resume.id);
      await browser.tabs.create({ url });
    });
  }

  function download(resume: Resume) {
    void perform(async () => {
      const url = await resumeApi.getDownloadUrl(resume.id);
      const response = await fetch(url, { signal: AbortSignal.timeout(60000) });
      if (!response.ok) throw new Error(`Download failed (${response.status}).`);
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = objectUrl; link.download = resume.name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    });
  }

  return (
    <section className="screen resume-vault" aria-labelledby="resume-vault-title">
      <p className="eyebrow">Vault</p>
      <h2 id="resume-vault-title">Resume Vault</h2>

      <ResumeUpload onUploadComplete={() => { void refresh(); }} />
      <button disabled={loading || busy} onClick={() => void refresh()}>Refresh</button>
      {editing && (
        <form onSubmit={(event) => {
          event.preventDefault();
          void perform(async () => {
            const nextTags = tags.split(',').map((tag) => tag.trim()).filter(Boolean);
            if (!name.trim() || name.trim().length > 100 || nextTags.length > 10 || nextTags.some((tag) => tag.length > 30)) {
              throw new Error('Use a name of 1–100 characters and up to 10 tags of 1–30 characters.');
            }
            // Apply each response immediately, including when a later request fails.
            const renamed = await resumeApi.renameResume(editing.id, name.trim());
            setResumes((items) => items.map((item) => item.id === renamed.id ? renamed : item));
            const updated = await resumeApi.updateTags(editing.id, nextTags);
            setResumes((items) => items.map((item) => item.id === updated.id ? updated : item));
            setEditing(null);
          });
        }}>
          <label>Name <input value={name} maxLength={100} required disabled={busy} onChange={(event) => setName(event.target.value)} /></label>
          <label>Tags (comma separated) <input value={tags} disabled={busy} onChange={(event) => setTags(event.target.value)} /></label>
          <button disabled={busy} type="submit">Save</button>
          <button disabled={busy} type="button" onClick={() => setEditing(null)}>Cancel</button>
        </form>
      )}
      {deleting && (
        <div role="group" aria-label="Confirm deletion">
          <p>Delete {deleting.name}?</p>
          <button disabled={busy} onClick={() => void perform(async () => {
            await resumeApi.deleteResume(deleting.id);
            setResumes((items) => items.filter((item) => item.id !== deleting.id));
            setDeleting(null);
          })}>Delete</button>
          <button disabled={busy} onClick={() => setDeleting(null)}>Cancel</button>
        </div>
      )}
      <div className="resume-vault-summary">
        <span>{visibleResumes.length} {visibleResumes.length === 1 ? 'resume' : 'resumes'}</span>
      </div>

      <p className="resume-notice" role="status">{notice}</p>

      {visibleResumes.length > 0 ? (
        <ul className="resume-list" aria-label="Resumes">
          {visibleResumes.map((resume) => (
            <li key={resume.id} className="resume-row">
              <button className="resume-thumbnail" aria-label={`Preview ${resume.name}`} disabled={busy} onClick={() => preview(resume)}>
                <img className="resume-pdf-icon" src={pdfIcon} alt="" aria-hidden="true" />
              </button>
              <div className="resume-row-content">
                <h3><button className="resume-name" disabled={busy} onClick={() => preview(resume)}>{resume.name}</button></h3>
                <p className="resume-upload-date">
                  <time dateTime={resume.uploadedAt}>{uploadDate.format(new Date(resume.uploadedAt))}</time>
                </p>
                {resume.tags.length > 0 && (
                  <ul className="resume-tags" aria-label={`Tags for ${resume.name}`}>
                    {resume.tags.map((tag, index) => <li key={`${tag}-${index}`}>{tag}</li>)}
                  </ul>
                )}
              </div>
              <div className="resume-actions" onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) setOpenActions(null);
              }} onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setOpenActions(null);
                  event.currentTarget.querySelector('button')?.focus();
                }
              }}>
                <button className="resume-more" aria-label={`Actions for ${resume.name}`} aria-expanded={openActions === resume.id} aria-controls={`actions-${resume.id}`} onClick={() => setOpenActions(openActions === resume.id ? null : resume.id)}>⋯</button>
                {openActions === resume.id && (
                  <div className="resume-action-menu" id={`actions-${resume.id}`}>
                    <button disabled={busy} onClick={() => download(resume)}>Download</button>
                    <button disabled={busy} onClick={() => { setEditing(resume); setDeleting(null); setName(resume.name); setTags(resume.tags.join(', ')); setOpenActions(null); }}>Edit</button>
                    <button disabled={busy} onClick={() => { setDeleting(resume); setEditing(null); setOpenActions(null); }}>Delete</button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="resume-vault-empty">
          <h3>{loading ? 'Loading resumes…' : notice ? 'Could not load resumes' : 'No resumes yet'}</h3>
        </div>
      )}
    </section>
  );
}
