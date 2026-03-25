"""Custom evaluators for pydantic-evals."""

import re
from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext


@dataclass(repr=False)
class NumericContains(Evaluator):
    """Check if the output contains a number within tolerance of the expected value.

    Extracts all numbers from the output string (handling commas, decimals,
    currency symbols) and passes if any are within the relative tolerance.
    """

    value: float
    tolerance: float = 0.01  # 1% relative tolerance

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        text = str(ctx.output)
        # Match numbers with optional commas and decimals (e.g. "1,473.42", "13.84", "$500")
        numbers = re.findall(r"[\d,]+\.?\d*", text)
        for n in numbers:
            try:
                parsed = float(n.replace(",", ""))
                if abs(self.value) < 1e-9:
                    if abs(parsed) < 1e-9:
                        return True
                elif abs(parsed - self.value) / abs(self.value) <= self.tolerance:
                    return True
            except ValueError:
                continue
        return False
