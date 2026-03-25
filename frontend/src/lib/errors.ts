const ERROR_MESSAGES: Record<string, string> = {
  empty_question: "Please enter a question.",
  question_too_long: "Your question is too long. Please keep it under 2,000 characters.",
  llm_timeout: "The AI took too long to respond. Please try again.",
  llm_rate_limited: "The AI service is busy. Please wait a moment and try again.",
  llm_auth_error: "Unable to authenticate with the AI service.",
  llm_unavailable: "Cannot reach the AI service. Please try again later.",
  request_timeout: "Your request timed out. Try a simpler question.",
  internal_error: "Something went wrong. Please try again.",
  stream_interrupted: "The response was interrupted. Please try again.",
};

const RETRYABLE_CODES = new Set([
  "llm_timeout",
  "llm_rate_limited",
  "llm_unavailable",
  "request_timeout",
  "internal_error",
  "stream_interrupted",
]);

export function getErrorMessage(errorCode: string | null | undefined, fallback?: string): string {
  if (errorCode && errorCode in ERROR_MESSAGES) {
    return ERROR_MESSAGES[errorCode];
  }
  return fallback || "Something went wrong. Please try again.";
}

export function isRetryable(errorCode: string | null | undefined): boolean {
  return !!errorCode && RETRYABLE_CODES.has(errorCode);
}
