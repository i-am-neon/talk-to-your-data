from dataclasses import dataclass, field

import logfire
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.tools import execute_python_code, ExecutionResult
from app.config import settings

logfire.configure(
    token=settings.logfire_token if settings.logfire_token else None,
    send_to_logfire=bool(settings.logfire_token),
)


@dataclass
class AgentDeps:
    df_schema: str
    results: list[ExecutionResult] = field(default_factory=list)


model = OpenAIChatModel(
    settings.litellm_model,
    provider=OpenAIProvider(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    ),
)

agent = Agent(
    model,
    deps_type=AgentDeps,
    retries=3,
)


@agent.system_prompt
def build_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return f"""\
You are a data analyst assistant. Users ask questions about a dataset in plain English.
You have access to a pandas DataFrame loaded as `df`.

{ctx.deps.df_schema}

Instructions:
- Write Python code using pandas to answer the user's question.
- Use print() to output text/numeric results.
- Use matplotlib/seaborn with plt.show() for charts when visualization is appropriate.
- For tabular results, print the DataFrame (it will be formatted as a table).
- Always provide a clear, concise text explanation along with any code output.
- If the question is unclear or cannot be answered with the data, explain why and suggest alternatives.
"""


@agent.tool
def run_code(ctx: RunContext[AgentDeps], code: str) -> str:
    """Execute Python code to analyze the dataset.

    The DataFrame is pre-loaded as `df`. pandas, numpy, matplotlib, and seaborn are available.
    Use plt.show() to display charts. Use print() to output text results.

    Args:
        code: Python code to execute. `df` is already loaded with the dataset.
    """
    result = execute_python_code(code)
    ctx.deps.results.append(result)

    if result.error:
        raise ModelRetry(
            f"Code execution failed:\n{result.error}\n"
            "Fix the code and try again."
        )

    # Build response for the LLM
    response_parts = []
    if result.stdout:
        response_parts.append(f"Output:\n{result.stdout}")
    if result.images:
        response_parts.append(f"{len(result.images)} chart(s) generated and will be shown to the user.")
    if not response_parts:
        response_parts.append("Code executed successfully with no output.")

    return "\n\n".join(response_parts)
