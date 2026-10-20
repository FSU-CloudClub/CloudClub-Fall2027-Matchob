import { useRef, useState } from 'react';
import { Button } from '../components/Button';
import {
  mockApplicationDetection,
  simulateAutofill,
  type MockAutofillResult,
} from '../mocks/autofill';

type AutofillStatus = 'idle' | 'loading' | 'success' | 'error';

export function AutoFillReviewScreen() {
  const [detection] = useState(mockApplicationDetection);
  const [status, setStatus] = useState<AutofillStatus>('idle');
  const [result, setResult] = useState<MockAutofillResult | null>(null);
  const attemptCount = useRef(0);

  async function handleAutofill() {
    if (status === 'loading' || !detection.detected) return;

    attemptCount.current += 1;
    setStatus('loading');
    setResult(null);

    try {
      const response = await simulateAutofill(attemptCount.current);
      setResult(response);
      setStatus('success');
    } catch {
      setStatus('error');
    }
  }

  return (
    <section className="screen autofill-screen" aria-labelledby="autofill-title">
      <div className="autofill-heading">
        <p className="autofill-eyebrow">Application assistant <span>01 / 01</span></p>
        <h2 id="autofill-title">Make the first move.</h2>
        <p>Preview sample application details alongside the job page.</p>
      </div>

      <div className="autofill-detection">
        <span className="autofill-detection-icon" aria-hidden="true">{detection.detected ? '✓' : '−'}</span>
        <div>
          <strong>{detection.detected ? 'Application detected' : 'No application detected'}</strong>
          <span>{detection.description}</span>
        </div>
        <span className="autofill-mock-tag">Mock</span>
      </div>

      <div className="autofill-action">
        <div className="autofill-action-copy">
          <span>READY WHEN YOU ARE</span>
          <strong>Fill sample application fields</strong>
        </div>
        <Button onClick={handleAutofill} disabled={status === 'loading' || !detection.detected}>
          {status === 'loading' && <span className="autofill-spinner" aria-hidden="true" />}
          Autofill Application
          {status !== 'loading' && <span className="autofill-arrow" aria-hidden="true">↗</span>}
        </Button>
      </div>

      <div className="autofill-summary" role={status === 'error' ? 'alert' : 'status'}>
        <div className="autofill-count">
          <strong>{result?.fields.length ?? 0}</strong>
          <span>fields filled</span>
        </div>
        <div className="autofill-summary-copy">
          <strong>
            {status === 'loading' && 'Autofill in progress'}
            {status === 'success' && 'Autofill complete'}
            {status === 'error' && 'Autofill could not complete'}
            {status === 'idle' && (detection.detected ? 'Ready to autofill' : 'Waiting for an application')}
          </strong>
          <span>
            {status === 'loading' && 'Filling sample fields now…'}
            {status === 'success' && 'Your sample results are ready to review.'}
            {status === 'error' && 'This sample run failed. Use the button to retry.'}
            {status === 'idle' && (detection.detected ? 'Run the sample to see your results.' : 'No sample form is available yet.')}
          </span>
        </div>
      </div>

      <div className="autofill-review">
        <div className="autofill-review-heading">
          <h3>Field review</h3>
          <span>{result ? `${result.fields.length} fields` : 'Preview'}</span>
        </div>
        {result ? (
          <ul className="autofill-fields">
            {result.fields.map((field) => (
              <li key={field.label}>
                <span>{field.label}</span>
                <strong>{field.value}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className="autofill-empty">
            {status === 'error' ? 'No fields were filled. Retry to view sample results.' : 'Sample field results will appear here.'}
          </p>
        )}
      </div>
    </section>
  );
}
