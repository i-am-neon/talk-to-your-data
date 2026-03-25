import asyncio
from enum import Enum

import httpx


class ErrorCode(str, Enum):
    EMPTY_QUESTION = "empty_question"
    QUESTION_TOO_LONG = "question_too_long"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMITED = "llm_rate_limited"
    LLM_AUTH_ERROR = "llm_auth_error"
    LLM_UNAVAILABLE = "llm_unavailable"
    REQUEST_TIMEOUT = "request_timeout"
    INTERNAL_ERROR = "internal_error"


USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.EMPTY_QUESTION: "Please enter a question.",
    ErrorCode.QUESTION_TOO_LONG: "Your question is too long. Please keep it under 2,000 characters.",
    ErrorCode.LLM_TIMEOUT: "The AI took too long to respond. Please try again.",
    ErrorCode.LLM_RATE_LIMITED: "The AI service is busy. Please wait a moment and try again.",
    ErrorCode.LLM_AUTH_ERROR: "Unable to authenticate with the AI service.",
    ErrorCode.LLM_UNAVAILABLE: "Cannot reach the AI service. Please try again later.",
    ErrorCode.REQUEST_TIMEOUT: "Your request timed out. Try asking a simpler question.",
    ErrorCode.INTERNAL_ERROR: "Something went wrong. Please try again.",
}

MAX_QUESTION_LENGTH = 2000
REQUEST_TIMEOUT_SECONDS = 120  # 2 minutes


def classify_error(exc: Exception) -> tuple[ErrorCode, str]:
    """Classify an exception into an error code and user-facing message."""
    if isinstance(exc, asyncio.TimeoutError):
        return ErrorCode.REQUEST_TIMEOUT, USER_MESSAGES[ErrorCode.REQUEST_TIMEOUT]

    if isinstance(exc, httpx.TimeoutException):
        return ErrorCode.LLM_TIMEOUT, USER_MESSAGES[ErrorCode.LLM_TIMEOUT]

    if isinstance(exc, httpx.ConnectError):
        return ErrorCode.LLM_UNAVAILABLE, USER_MESSAGES[ErrorCode.LLM_UNAVAILABLE]

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return ErrorCode.LLM_RATE_LIMITED, USER_MESSAGES[ErrorCode.LLM_RATE_LIMITED]
        if status in (401, 403):
            return ErrorCode.LLM_AUTH_ERROR, USER_MESSAGES[ErrorCode.LLM_AUTH_ERROR]
        return ErrorCode.LLM_UNAVAILABLE, USER_MESSAGES[ErrorCode.LLM_UNAVAILABLE]

    return ErrorCode.INTERNAL_ERROR, USER_MESSAGES[ErrorCode.INTERNAL_ERROR]
