import asyncio
import httpx
from app.errors import classify_error, ErrorCode, USER_MESSAGES, MAX_QUESTION_LENGTH


def test_classify_asyncio_timeout():
    code, msg = classify_error(asyncio.TimeoutError())
    assert code == ErrorCode.REQUEST_TIMEOUT
    assert msg == USER_MESSAGES[ErrorCode.REQUEST_TIMEOUT]


def test_classify_httpx_timeout():
    exc = httpx.ReadTimeout("timed out")
    code, msg = classify_error(exc)
    assert code == ErrorCode.LLM_TIMEOUT
    assert msg == USER_MESSAGES[ErrorCode.LLM_TIMEOUT]


def test_classify_httpx_connect_error():
    exc = httpx.ConnectError("connection refused")
    code, msg = classify_error(exc)
    assert code == ErrorCode.LLM_UNAVAILABLE
    assert msg == USER_MESSAGES[ErrorCode.LLM_UNAVAILABLE]


def test_classify_httpx_429():
    response = httpx.Response(429, request=httpx.Request("POST", "http://test"))
    exc = httpx.HTTPStatusError("rate limited", request=response.request, response=response)
    code, msg = classify_error(exc)
    assert code == ErrorCode.LLM_RATE_LIMITED
    assert msg == USER_MESSAGES[ErrorCode.LLM_RATE_LIMITED]


def test_classify_httpx_401():
    response = httpx.Response(401, request=httpx.Request("POST", "http://test"))
    exc = httpx.HTTPStatusError("unauthorized", request=response.request, response=response)
    code, msg = classify_error(exc)
    assert code == ErrorCode.LLM_AUTH_ERROR
    assert msg == USER_MESSAGES[ErrorCode.LLM_AUTH_ERROR]


def test_classify_httpx_500():
    response = httpx.Response(500, request=httpx.Request("POST", "http://test"))
    exc = httpx.HTTPStatusError("server error", request=response.request, response=response)
    code, msg = classify_error(exc)
    assert code == ErrorCode.LLM_UNAVAILABLE
    assert msg == USER_MESSAGES[ErrorCode.LLM_UNAVAILABLE]


def test_classify_generic_exception():
    code, msg = classify_error(RuntimeError("something broke"))
    assert code == ErrorCode.INTERNAL_ERROR
    assert msg == USER_MESSAGES[ErrorCode.INTERNAL_ERROR]


def test_max_question_length_is_reasonable():
    assert MAX_QUESTION_LENGTH == 2000
