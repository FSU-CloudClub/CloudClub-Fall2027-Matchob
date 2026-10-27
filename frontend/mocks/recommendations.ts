import type { Recommendation } from '../types';

// Local sample content keeps the review screen usable without a backend.
export const mockRecommendations: Recommendation[] = [
  {
    id: '1',
    suggestion: 'Highlight relevant project experience.',
    reason: 'The job description emphasizes hands-on work.',
  },
  {
    id: '2',
    suggestion: 'Use clear, measurable outcomes in bullet points.',
    reason: 'Specific results make experience easier to evaluate.',
  },
];
