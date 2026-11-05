import { useState } from 'react';
import { browser } from 'wxt/browser';
import { AppLayout } from '../../components/AppLayout';
import { Button } from '../../components/Button';
import { ResumeVault } from '../../features/resumes/ResumeVault';
import { JobDescriptionScreen } from '../../pages/JobDescriptionScreen';
import { LandingScreen } from '../../pages/LandingScreen';
import { RecommendationReviewScreen } from '../../pages/RecommendationReviewScreen';
import { SupportingContextScreen } from '../../pages/SupportingContextScreen';
import { flowSteps } from '../../utils/flow';

const popupPages = [
  { label: flowSteps[0], Screen: LandingScreen },
  { label: flowSteps[1], Screen: ResumeVault },
  { label: flowSteps[2], Screen: JobDescriptionScreen },
  { label: flowSteps[3], Screen: SupportingContextScreen },
  { label: flowSteps[4], Screen: RecommendationReviewScreen },
] as const;

export function App() {
  const [step, setStep] = useState(0);
  const [panelError, setPanelError] = useState<string | null>(null);
  const Screen = popupPages[step]?.Screen ?? LandingScreen;

  function openAutofillPanel() {
    if (!browser.sidePanel?.open) {
      setPanelError('The side panel requires a newer version of Chrome.');
      return;
    }

    setPanelError(null);
    browser.sidePanel.open({ windowId: browser.windows.WINDOW_ID_CURRENT })
      .then(() => window.close())
      .catch(() => setPanelError('Could not open the side panel. Please try again.'));
  }

  return (
    <AppLayout defaultTheme="light">
      <Screen />

      {step === 0 ? (
        <Button onClick={() => setStep(1)}>Get Started</Button>
      ) : (
        <div className="navigation">
          <Button variant="secondary" onClick={() => { setPanelError(null); setStep(step - 1); }}>Back</Button>
          {step < popupPages.length - 1 ? (
            <Button onClick={() => setStep(step + 1)}>Next</Button>
          ) : (
            <Button onClick={openAutofillPanel}>Open side panel</Button>
          )}
        </div>
      )}
      {panelError && <p className="panel-error" role="alert">{panelError}</p>}
      <p className="step-label">{popupPages[step]?.label} · {step + 1} of {flowSteps.length}</p>
    </AppLayout>
  );
}
