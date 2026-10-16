import { mockRecommendations } from '../mocks/recommendations';

export function RecommendationReviewScreen() {
  return (
    <section className="screen">
      <p className="eyebrow">Sample data</p>
      <h2>Recommendation review</h2>
      <p>Future recommendations will appear here. For now, preview mock suggestions:</p>
      <ul className="sample-list">
        {mockRecommendations.map((item) => <li key={item.id}>{item.suggestion}</li>)}
      </ul>
    </section>
  );
}
