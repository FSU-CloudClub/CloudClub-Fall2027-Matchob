import { useState } from 'react';
import { Button } from '../../components/Button';
import { ResumeVault } from '../../features/resumes/ResumeVault';
import { AutoFillReviewScreen } from '../../pages/AutoFillReviewScreen';
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
  AutoFillReviewScreen,
];

export function App() {
  // TODO: Sprint 1 - Frontend Layout + Nav: replace preview steps with product navigation.
  const [step, setStep] = useState(0);
  const Screen = screens[step] ?? LandingScreen;

  return (
    <main className="popup">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <span>Matchob</span>
      </header>

      <Screen />

      {step === 0 ? (
        <Button onClick={() => setStep(1)}>Get Started</Button>
      ) : (
        <div className="navigation">
          <Button variant="secondary" onClick={() => setStep(step - 1)}>Back</Button>
          {step < flowSteps.length - 1 && (
            <Button onClick={() => setStep(step + 1)}>Next</Button>
          )}
        </div>
      )}
      <p className="step-label">{flowSteps[step]} · {step + 1} of {flowSteps.length}</p>
    </main>
  );
}
