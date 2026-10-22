import { useState } from 'react';
import { mockResumes } from '../../mocks/resumes';
import type { Resume } from '../../types';
import pdfIcon from '../../assets/icons/file-earmark-pdf.svg';
import './ResumeVault.css';

const uploadDate = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

type ResumeVaultProps = {
  resumes?: Resume[];
};

export function ResumeVault({ resumes = mockResumes }: ResumeVaultProps = {}) {
  const [openActions, setOpenActions] = useState<string | null>(null);
  const [notice, setNotice] = useState('');

  function placeholder(action: string, name: string) {
    setNotice(`${action} for ${name} is not available yet.`);
    setOpenActions(null);
  }

  return (
    <section className="screen resume-vault" aria-labelledby="resume-vault-title">
      <p className="eyebrow">Vault</p>
      <h2 id="resume-vault-title">Resume Vault</h2>

      <div className="resume-vault-summary">
        <span>{resumes.length} {resumes.length === 1 ? 'resume' : 'resumes'}</span>
      </div>

      <p className="resume-notice" role="status">{notice}</p>

      {resumes.length > 0 ? (
        <ul className="resume-list" aria-label="Saved resumes">
          {resumes.map((resume) => (
            <li key={resume.id} className="resume-row">
              <button className="resume-thumbnail" aria-label={`Preview ${resume.name}`} onClick={() => placeholder('Preview', resume.name)}>
                <img className="resume-pdf-icon" src={pdfIcon} alt="" aria-hidden="true" />
              </button>
              <div className="resume-row-content">
                <h3><button className="resume-name" onClick={() => placeholder('Preview', resume.name)}>{resume.name}</button></h3>
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
                    {['Download', 'Edit', 'Delete'].map((action) => (
                      <button key={action} onClick={() => placeholder(action, resume.name)}>{action}</button>
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
    </section>
  );
}
