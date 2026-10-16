// Small starting shapes; expand these when the MVP data contract is agreed on.
export type Resume = {
  id: string;
  fileName: string;
  text?: string;
};

export type JobDescription = {
  title: string;
  company?: string;
  text: string;
};

export type Recommendation = {
  id: string;
  suggestion: string;
  reason: string;
};
