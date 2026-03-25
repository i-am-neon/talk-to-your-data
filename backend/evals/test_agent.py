import pytest
from pydantic_evals import Dataset
from pydantic_evals.evaluators.llm_as_a_judge import set_default_judge_model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.agent import agent, AgentDeps
from app.config import settings
from app.data.loader import load_dataset, get_schema_summary

_df = load_dataset()
_schema = get_schema_summary(_df)

# Use the same LiteLLM proxy for LLM-as-judge evaluations
_judge_provider = OpenAIProvider(
    base_url=settings.litellm_base_url,
    api_key=settings.litellm_api_key,
)
set_default_judge_model(OpenAIChatModel(settings.litellm_model, provider=_judge_provider))


async def run_agent(question: str) -> str:
    deps = AgentDeps(df_schema=_schema)
    result = await agent.run(question, deps=deps)
    return result.output


@pytest.mark.asyncio
async def test_eval():
    dataset = Dataset.from_file("evals/cases.yaml")
    report = await dataset.evaluate(run_agent)
    report.print(include_input=True, include_output=True)
    assert not report.failures, f"{len(report.failures)} case(s) failed to execute"
    for case in report.cases:
        failed = {k: v for k, v in case.assertions.items() if not v}
        assert not failed, f"Case '{case.name}' failed assertions: {failed}"


@pytest.mark.asyncio
async def test_chart_generation():
    """Agent should produce a matplotlib image when asked for a chart."""
    deps = AgentDeps(df_schema=_schema)
    result = await agent.run("Plot ARR distribution as a histogram", deps=deps)
    images = [img for r in deps.results for img in r.images]
    assert len(images) > 0, f"Expected chart image but got none. Output: {result.output}"
