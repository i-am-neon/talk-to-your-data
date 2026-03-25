"""Red team eval suite — tests agent resilience against adversarial inputs."""

import pytest
from pydantic_evals import Dataset

from app.agent.agent import agent, AgentDeps
from app.data.loader import load_dataset, get_schema_summary
from evals.red_team_evaluator import RedTeamJudge

_df = load_dataset()
_schema = get_schema_summary(_df)


async def run_agent(question: str) -> str:
    deps = AgentDeps(df_schema=_schema)
    result = await agent.run(question, deps=deps)
    return result.output


@pytest.mark.asyncio
async def test_red_team():
    dataset = Dataset.from_file(
        "evals/red_team_cases.yaml",
        custom_evaluator_types=[RedTeamJudge],
    )
    report = await dataset.evaluate(run_agent)
    report.print(include_input=True, include_output=True)

    assert not report.failures, f"{len(report.failures)} case(s) failed to execute"
    for case in report.cases:
        failed = {k: v for k, v in case.assertions.items() if not v}
        assert not failed, f"Case '{case.name}' failed assertions: {failed}"
