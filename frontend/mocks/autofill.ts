export type MockAutofillResult = {
  fields: { label: string; value: string }[];
};

export const mockApplicationDetection = {
  detected: true,
  description: 'Sample job application form',
};

const mockAutofillResult: MockAutofillResult = {
  fields: [
    { label: 'Full name', value: 'Jordan Lee' },
    { label: 'Email', value: 'jordan.lee@example.com' },
    { label: 'Location', value: 'Tallahassee, FL' },
    { label: 'Work authorization', value: 'Authorized' },
  ],
};

// Alternate outcomes so the popup can preview success, error, and retry states.
export async function simulateAutofill(attempt: number): Promise<MockAutofillResult> {
  await new Promise((resolve) => setTimeout(resolve, 1200));

  if (attempt % 2 === 0) {
    throw new Error('Mock autofill failure');
  }

  return { fields: mockAutofillResult.fields.map((field) => ({ ...field })) };
}
