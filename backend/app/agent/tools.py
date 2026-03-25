import json
from dataclasses import dataclass

from e2b_code_interpreter import Sandbox

from app.config import settings
from app.data.loader import CSV_PATH

LAUNCH_CODE = """\
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json as _json
sns.set_theme()

_VALID_CHART_TYPES = ("bar", "line", "area", "pie", "radar")

def print_chart(chart_type, data, x_key, series, **kwargs):
    assert chart_type in _VALID_CHART_TYPES, f"Unknown chart type: {chart_type}. Use one of {_VALID_CHART_TYPES}"
    assert isinstance(data, list) and len(data) > 0, "data must be a non-empty list of dicts"
    assert isinstance(series, list) and len(series) > 0, "series must be a non-empty list"
    print("__CHART_JSON__" + _json.dumps({
        "type": chart_type,
        "data": data,
        "x_key": x_key,
        "series": series,
        **kwargs
    }))

df = pd.read_csv('/tmp/data.csv')
"""

MAX_OUTPUT_LENGTH = 50_000


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    images: list[str]  # base64 PNG strings
    code: str = ""
    error: str | None = None
    chart: dict | None = None


def _parse_chart_from_stdout(stdout: str) -> tuple[str, dict | None]:
    """Extract __CHART_JSON__ from stdout. Returns (clean_stdout, chart_dict_or_None)."""
    chart = None
    clean_lines = []
    for line in stdout.splitlines():
        if line.startswith("__CHART_JSON__"):
            try:
                chart = json.loads(line[len("__CHART_JSON__"):])
            except json.JSONDecodeError:
                clean_lines.append(line)  # keep malformed line in output
        else:
            clean_lines.append(line)
    return "\n".join(clean_lines), chart


def execute_python_code(code: str) -> ExecutionResult:
    """Execute Python code in an E2B sandbox. Returns structured result."""
    sbx = Sandbox.create(api_key=settings.e2b_api_key, timeout=60)
    try:
        # Upload CSV to sandbox
        with open(CSV_PATH, "rb") as f:
            sbx.files.write("/tmp/data.csv", f.read())

        # Run launch code
        sbx.run_code(LAUNCH_CODE)

        # Execute user code
        execution = sbx.run_code(code, timeout=30)

        stdout = "\n".join(execution.logs.stdout)
        stderr = "\n".join(execution.logs.stderr)

        # Parse chart JSON from stdout (before truncation to avoid losing marker)
        stdout, chart = _parse_chart_from_stdout(stdout)

        # Truncate long output
        if len(stdout) > MAX_OUTPUT_LENGTH:
            stdout = stdout[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"
        if len(stderr) > MAX_OUTPUT_LENGTH:
            stderr = stderr[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"

        # Collect images
        images = []
        for result in execution.results:
            if hasattr(result, "png") and result.png:
                images.append(result.png)

        error = None
        if execution.error:
            error = f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}"

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            images=images,
            code=code,
            error=error,
            chart=chart,
        )

    finally:
        sbx.kill()
