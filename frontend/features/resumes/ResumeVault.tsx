import { useCallback, useState } from 'react';
import { mockResumes } from '../../mocks/resumes';
import type { Resume } from '../../types';
import pdfIcon from '../../assets/icons/file-earmark-pdf.svg';
import wordIcon from '../../assets/icons/file-earmark-word.svg';
import { kindFromContentType, type ResumeFileKind } from './resumeFileTypes';
import { ResumeUpload } from './ResumeUpload';
import { ResumeDeleteDialog } from './ResumeDeleteDialog';
import { useResumeDelete } from './useResumeDelete';
import './ResumeVault.css';
import { ResumeTagsRename } from './ResumeTagsRename';
import { downloadResume } from '../../services/resumeFiles';
import { openResumePreview } from './ResumePreviewDownload';

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

type ResumeVaultProps = {
  resumes?: Resume[];
};

const previewResumes: Resume[] = Array.from({ length: 10 }, (_, index) =>
  mockResumes.map((resume) => ({ ...resume, id: `${resume.id}-preview-${index}` })),
).flat();

export function ResumeVault({ resumes = previewResumes }: ResumeVaultProps = {}) {
  const [view, setView] = useState<'saved' | 'upload'>('saved');
  const [openActions, setOpenActions] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [uploadedResumes, setUploadedResumes] = useState<Resume[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedResumes, setEditedResumes] = useState<Record<string, Resume>>({});

  const visibleResumes = [...uploadedResumes, ...resumes].map(
    (resume) => editedResumes[resume.id] ?? resume,
  );
  // `resumes` comes in as a prop, so deletions are tracked here and filtered out.
  const [deletedIds, setDeletedIds] = useState<Set<string>>(() => new Set());

  const visibleResumes = [...uploadedResumes, ...resumes].filter(
    (resume) => !deletedIds.has(resume.id),
  );

  const handleDeleted = useCallback((deleted: Resume) => {
    setDeletedIds((current) => new Set(current).add(deleted.id));
    setUploadedResumes((current) => current.filter((resume) => resume.id !== deleted.id));
    setNotice(`Deleted ${deleted.name}.`);
  }, []);

  const resumeDelete = useResumeDelete(handleDeleted);

  async function handleDownload(resume: Resume) {
    setDownloadingId(resume.id);
    setNotice('Preparing download…');
    setOpenActions(null);
    try {
      await downloadResume(resume.id, resume.name);
      setNotice('Download started.');
    } catch { setNotice('Download failed. Please try again from the resume menu.'); }
    finally { setDownloadingId(null); }
  }

  function placeholder(action: string, name: string) {
    setNotice(`${action} for ${name} is not available yet.`);
    setOpenActions(null);
  }

  function handleAction(action: string, resume: Resume) {
    if (action === 'Delete') {
      setOpenActions(null);
      setNotice('');
      resumeDelete.request(resume);
      return;
    }
    placeholder(action, resume.name);
  }

  return (
    <section className="screen resume-vault" aria-labelledby="resume-vault-title">
      <p className="eyebrow">Vault</p>
      <h2 id="resume-vault-title">Resume Vault</h2>

      <div className="resume-view-switch" role="group" aria-label="Resume view">
        <button type="button" aria-pressed={view === 'saved'} onClick={() => setView('saved')}>Saved resumes</button>
        <button type="button" aria-pressed={view === 'upload'} onClick={() => setView('upload')}>Upload new</button>
      </div>

      {view === 'upload' && <ResumeUpload onUploadComplete={(result, file) => {
        setUploadedResumes((current) => [{
          id: result.key,
          name: file.name,
          tags: [],
          contentType: result.contentType,
          uploadedAt: new Date().toISOString(),
        }, ...current]);
        setView('saved');
      }} />}

      {view === 'saved' && <>
      <div className="resume-vault-summary">
        <span>{visibleResumes.length} {visibleResumes.length === 1 ? 'resume' : 'resumes'}</span>
      </div>

      <p className="resume-notice" role="status">{notice}</p>

      {visibleResumes.length > 0 ? (
        <ul className="resume-list" aria-label="Resume preview list">
          {visibleResumes.map((resume) => (
            <li key={resume.id} className="resume-row">
              <button className="resume-thumbnail" aria-label={`Preview ${resume.name}`} onClick={() => placeholder('Preview', resume.name)}>
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
                    onSave={(updatedResume) => {
                      setEditedResumes((current) => ({ ...current, [updatedResume.id]: updatedResume }));
                      setEditingId(null);
                      setNotice(`Updated ${updatedResume.name}.`);
                    }}
                    onCancel={() => setEditingId(null)}
                  />
                ) : (
                  <>
                <h3><button className="resume-name" onClick={() => placeholder('Preview', resume.name)}>{resume.name}</button></h3>
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
                    {['Download', 'Edit', 'Delete'].map((action) => (
                      <button key={action} onClick={() => {
                        if (action === 'Edit') {
                          setEditingId(resume.id);
                          setOpenActions(null);
                          setNotice('');
                        } else {
                          placeholder(action, resume.name);
                        }
                      }}>{action}</button>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="resume-vault-empty">
          <h3>No resumes exist</h3>
        </div>
      )}
      </>}
    </section>
  );
}