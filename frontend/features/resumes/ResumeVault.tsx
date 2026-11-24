import { useCallback, useEffect, useState } from 'react';
import { resumeApi } from '../../services/resumeApi';
import { downloadResume } from '../../services/resumeFiles';
import type { Resume } from '../../types';
import pdfIcon from '../../assets/icons/file-earmark-pdf.svg';
import wordIcon from '../../assets/icons/file-earmark-word.svg';
import { kindFromContentType, type ResumeFileKind } from './resumeFileTypes';
import { ResumeUpload } from './ResumeUpload';
import { ResumeDeleteDialog } from './ResumeDeleteDialog';
import { useResumeDelete } from './useResumeDelete';
import { ResumeTagsRename } from './ResumeTagsRename';
import { openResumePreview } from './ResumePreviewDownload';
import './ResumeVault.css';

const uploadDate = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

const FILE_ICONS: Record<ResumeFileKind, string> = {
  pdf: pdfIcon,
  docx: wordIcon,
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function ResumeVault() {
  const [view, setView] = useState<'saved' | 'upload'>('saved');
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [openActions, setOpenActions] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [notice, setNotice] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setResumes(await resumeApi.getResumes());
      setLoadFailed(false);
      setNotice('');
    } catch (error) {
      setLoadFailed(true);
      setNotice(errorMessage(error, 'Could not load resumes.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const handleDeleted = useCallback((deleted: Resume) => {
    setResumes((current) => current.filter((resume) => resume.id !== deleted.id));
    setNotice(`Deleted ${deleted.name}.`);
  }, []);

  const resumeDelete = useResumeDelete(handleDeleted);

  function replaceResume(updated: Resume) {
    setResumes((current) => current.map((resume) => (resume.id === updated.id ? updated : resume)));
  }

  async function handleSave(original: Resume, edited: Resume) {
    setSavingId(original.id);
    setNotice('');
    try {
      // Apply each response immediately, so a later failure keeps earlier changes visible.
      if (edited.name !== original.name) {
        replaceResume(await resumeApi.renameResume(original.id, edited.name));
      }
      const tagsChanged =
        edited.tags.length !== original.tags.length ||
        edited.tags.some((tag, index) => tag !== original.tags[index]);
      if (tagsChanged) {
        replaceResume(await resumeApi.updateTags(original.id, edited.tags));
      }
      setEditingId(null);
      setNotice(`Updated ${edited.name}.`);
    } catch (error) {
      setNotice(errorMessage(error, 'Could not save changes. Please try again.'));
    } finally {
      setSavingId(null);
    }
  }

  async function handleDownload(resume: Resume) {
    setDownloadingId(resume.id);
    setNotice('Preparing download…');
    setOpenActions(null);
    try {
      await downloadResume(resume.id, resume.name);
      setNotice('Download started.');
    } catch (error) {
      setNotice(errorMessage(error, 'Download failed. Please try again from the resume menu.'));
    } finally {
      setDownloadingId(null);
    }
  }

  function handlePreview(resume: Resume) {
    setOpenActions(null);
    if (kindFromContentType(resume.contentType) !== 'pdf') {
      setNotice('Preview is only available for PDFs. Use Download from the resume menu instead.');
      return;
    }
    void openResumePreview(resume).catch(() => setNotice('Could not open preview. Please try again.'));
  }

  function handleAction(action: 'Download' | 'Edit' | 'Delete', resume: Resume) {
    setOpenActions(null);
    setNotice('');
    if (action === 'Download') void handleDownload(resume);
    else if (action === 'Edit') setEditingId(resume.id);
    else resumeDelete.request(resume);
  }

  return (
    <section className="screen resume-vault" aria-labelledby="resume-vault-title">
      <p className="eyebrow">Vault</p>
      <h2 id="resume-vault-title">Resume Vault</h2>

      <div className="resume-view-switch" role="group" aria-label="Resume view">
        <button type="button" aria-pressed={view === 'saved'} onClick={() => setView('saved')}>Saved resumes</button>
        <button type="button" aria-pressed={view === 'upload'} onClick={() => setView('upload')}>Upload new</button>
      </div>

      {view === 'upload' && <ResumeUpload onUploadComplete={() => {
        setView('saved');
        void refresh();
      }} />}

      {view === 'saved' && <>
      <div className="resume-vault-summary">
        <span>{resumes.length} {resumes.length === 1 ? 'resume' : 'resumes'}</span>
        <button type="button" disabled={loading} onClick={() => void refresh()}>Refresh</button>
      </div>

      <p className="resume-notice" role="status">{notice}</p>

      {resumes.length > 0 ? (
        <ul className="resume-list" aria-label="Resumes">
          {resumes.map((resume) => (
            <li key={resume.id} className="resume-row">
              <button className="resume-thumbnail" aria-label={`Preview ${resume.name}`} onClick={() => handlePreview(resume)}>
                <img
                  className="resume-file-icon"
                  src={FILE_ICONS[kindFromContentType(resume.contentType)]}
                  alt=""
                  aria-hidden="true"
                />
              </button>
              <div className="resume-row-content">
                {editingId === resume.id ? (
                  <ResumeTagsRename
                    resume={resume}
                    initialEditing
                    onSave={(edited) => { if (savingId !== resume.id) void handleSave(resume, edited); }}
                    onCancel={() => setEditingId(null)}
                  />
                ) : (
                  <>
                <h3><button className="resume-name" onClick={() => handlePreview(resume)}>{resume.name}</button></h3>
                <p className="resume-upload-date">
                  <time dateTime={resume.uploadedAt}>{uploadDate.format(new Date(resume.uploadedAt))}</time>
                </p>
                {resume.tags.length > 0 && (
                  <ul className="resume-tags" aria-label={`Tags for ${resume.name}`}>
                    {resume.tags.map((tag, index) => <li key={`${tag}-${index}`}>{tag}</li>)}
                  </ul>
                )}
                  </>
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
                    {(['Download', 'Edit', 'Delete'] as const).map((action) => (
                      <button
                        key={action}
                        disabled={action === 'Download' && downloadingId === resume.id}
                        onClick={() => handleAction(action, resume)}
                      >{action}</button>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="resume-vault-empty">
          <h3>{loading ? 'Loading resumes…' : loadFailed ? 'Could not load resumes' : 'No resumes yet'}</h3>
        </div>
      )}
      </>}

      <ResumeDeleteDialog {...resumeDelete} />
    </section>
  );
}
