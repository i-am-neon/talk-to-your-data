from dataclasses import dataclass, field

import logfire
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.tools import execute_python_code, ExecutionResult
from app.config import settings, MODEL_IDS

logfire.configure(
    token=settings.logfire_token if settings.logfire_token else None,
    send_to_logfire=bool(settings.logfire_token),
)


@dataclass
class AgentDeps:
    df_schema: str
    results: list[ExecutionResult] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)


_provider = OpenAIProvider(
    base_url=settings.litellm_base_url,
    api_key=settings.litellm_api_key,
)

model = OpenAIChatModel(settings.litellm_model, provider=_provider)


def make_model(name: str) -> OpenAIChatModel:
    """Create a model instance for a given short name (e.g. 'opus', 'sonnet', 'haiku')."""
    model_id = MODEL_IDS.get(name, settings.litellm_model)
    return OpenAIChatModel(model_id, provider=_provider)

agent = Agent(
    model,
    deps_type=AgentDeps,
    retries=3,
)


@agent.system_prompt
def build_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    if ctx.deps.artifacts:
        artifact_list = "\n".join(
            f'- {a["id"]}: "{a["title"]}" ({a["type"]})'
            for a in ctx.deps.artifacts
        )
    else:
        artifact_list = "None"

    return f"""\
You are a data analyst. Users ask questions about a dataset in plain English.
You have access to a pandas DataFrame loaded as `df`.

{ctx.deps.df_schema}

## How to Respond
- Write Python code using pandas to answer the user's question.
- Use print() to output text/numeric results.
- For standard charts (bar, line, area, pie, radar), use print_chart() instead of matplotlib:
    monthly = df.groupby("month")["revenue"].sum().reset_index()
    print_chart("bar", monthly.to_dict(orient="records"),
                x_key="month",
                series=[{{"key": "revenue", "label": "Revenue"}}])
  The frontend renders these as interactive charts. Do NOT use plt.show() for these types.
- For complex visualizations (heatmaps, violin plots, multi-axis, annotations), use matplotlib with plt.show().
- For tabular results, print the DataFrame.
- If the question cannot be answered with the available data, say so and suggest what you can answer.

## Tone
- Be direct, professional, and confident. No hedging or filler.
- Be warm but concise — answer the question, not around the question.
- Never use emojis.
- Use precise language: "The average ARR is $4.2M" not "it appears the average ARR might be around $4.2M."
- State results plainly. When data is ambiguous, explain why briefly.

## Workspace Artifacts
The user's UI has a workspace panel next to the chat that displays artifacts (charts, tables, code outputs).
Artifacts appear separately from your chat message — the user can see them side by side.

Because artifacts are visible in the workspace, keep your chat response brief and conversational.
Do NOT repeat or describe artifact content in detail in your chat message.
Good: "Here's the breakdown of ARR by industry." or "I've updated the chart to use a pie layout."
Bad: Listing all the data points or describing what the chart shows in detail.

When you generate a chart or significant output, declare an artifact at the END of your response:

For new artifacts: [[artifact:create|<descriptive title>|<type>]]
For updating existing artifacts: [[artifact:update|<artifact_id>|<updated title>|<type>]]

Types: chart, table, code
Only declare ONE artifact per response. Only use "update" for artifacts listed below.

Current workspace artifacts:
{artifact_list}
"""


@agent.tool
def run_code(ctx: RunContext[AgentDeps], code: str) -> str:
    """Execute Python code to analyze the dataset.

    The DataFrame is pre-loaded as `df`. pandas, numpy, matplotlib, and seaborn are available.
    Use print_chart() for standard charts (bar, line, area, pie, radar).
    Use plt.show() only for complex visualizations. Use print() for text results.

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
    if result.chart:
        response_parts.append("Interactive chart generated and will be shown to the user.")
    if result.images:
        response_parts.append(f"{len(result.images)} chart image(s) generated and will be shown to the user.")
    if not response_parts:
        response_parts.append("Code executed successfully with no output.")

    return "\n\n".join(response_parts)
