import { ResumeUpload } from './ResumeUpload';

export function ResumeVault() {
  // TODO: Sprint 1 - Resume Vault UI: build the list, cards, and request states here.
  return (
    <section className="screen">
      <p className="eyebrow">Vault</p>
      <h2>Resume Vault</h2>
      <p>Resume management is a Sprint 1 team task.</p>
      <ResumeUpload />
    </section>
  );
}
