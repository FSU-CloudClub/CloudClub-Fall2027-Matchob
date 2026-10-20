import { useState } from 'react';
import { browser } from 'wxt/browser';
import { Button } from '../../components/Button';
import { ThemeToggle } from '../../components/ThemeToggle';
import { ResumeVault } from '../../features/resumes/ResumeVault';
import { JobDescriptionScreen } from '../../pages/JobDescriptionScreen';
import { LandingScreen } from '../../pages/LandingScreen';
import { RecommendationReviewScreen } from '../../pages/RecommendationReviewScreen';
import { SupportingContextScreen } from '../../pages/SupportingContextScreen';
import { flowSteps } from '../../utils/flow';

const screens = [
  LandingScreen,
  ResumeVault,
  JobDescriptionScreen,
  SupportingContextScreen,
  RecommendationReviewScreen,
];

export function App() {
  // TODO: Sprint 1 - Frontend Layout + Nav: replace preview steps with product navigation.
  const [step, setStep] = useState(0);
  const [panelError, setPanelError] = useState<string | null>(null);
  const Screen = screens[step] ?? LandingScreen;

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
    <main className="popup">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <span>Matchob</span>
        <ThemeToggle defaultTheme="light" />
      </header>

      <Screen />

      {step === 0 ? (
        <Button onClick={() => setStep(1)}>Get Started</Button>
      ) : (
        <div className="navigation">
          <Button variant="secondary" onClick={() => { setPanelError(null); setStep(step - 1); }}>Back</Button>
          {step < screens.length - 1 ? (
            <Button onClick={() => setStep(step + 1)}>Next</Button>
          ) : (
            <Button onClick={openAutofillPanel}>Open side panel</Button>
          )}
        </div>
      )}
      {panelError && <p className="panel-error" role="alert">{panelError}</p>}
      <p className="step-label">{flowSteps[step]} · {step + 1} of {flowSteps.length}</p>
    </main>
  );
}
