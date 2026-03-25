from dataclasses import dataclass
from pathlib import Path

from e2b_code_interpreter import Sandbox

from app.config import settings
from app.data.loader import CSV_PATH

LAUNCH_CODE = """\
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme()

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

        stdout = execution.logs.stdout
        stderr = execution.logs.stderr

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
        )

    finally:
        sbx.kill()
