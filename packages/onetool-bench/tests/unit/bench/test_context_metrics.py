"""Unit tests for multi-prompt task execution context metrics."""

import pytest

from bench.harness.metrics import LLMCallMetrics, TaskResult
from bench.harness.runner import split_prompts


@pytest.mark.unit
@pytest.mark.bench
class TestMultiPromptScenarios:
    """Tests for multi-prompt task execution with realistic data."""

    def test_split_prompts_multi_step(self) -> None:
        """split_prompts works with realistic multi-prompt YAML content."""
        prompt = """>>>
```python
npm = check_npm_versions(dependencies={"express": "4.0.0"})
```
Return only latest versions.
---PROMPT---
>>>
```python
pypi = check_pypi_versions(dependencies={"requests": "2.0.0"})
```
Return only latest versions.
---PROMPT---
Now combine all the results and list them as a markdown table with columns:
| Package | Current | Latest |"""

        prompts = split_prompts(prompt)

        assert len(prompts) == 3
        assert "check_npm_versions" in prompts[0]
        assert "check_pypi_versions" in prompts[1]
        assert "markdown table" in prompts[2]

    def test_metrics_accumulate_across_prompts(self) -> None:
        """Metrics accumulate correctly across a multi-prompt task."""
        metrics = [
            LLMCallMetrics(call_number=1, input_tokens=3000, output_tokens=200,
                           tool_calls_made=1, cumulative_input=3000, latency_ms=800),
            LLMCallMetrics(call_number=2, input_tokens=3500, output_tokens=150,
                           tool_calls_made=0, cumulative_input=6500, latency_ms=600),
            LLMCallMetrics(call_number=3, input_tokens=4000, output_tokens=250,
                           tool_calls_made=1, cumulative_input=10500, latency_ms=900),
            LLMCallMetrics(call_number=4, input_tokens=4600, output_tokens=180,
                           tool_calls_made=0, cumulative_input=15100, latency_ms=700),
            LLMCallMetrics(call_number=5, input_tokens=5200, output_tokens=400,
                           tool_calls_made=0, cumulative_input=20300, latency_ms=1100),
        ]
        task = TaskResult(
            name="multi-prompt-test", server="onetool", model="test",
            prompt="Multi-prompt task", response="Final summary table",
            input_tokens=20300, output_tokens=1180, llm_calls=5, tool_calls=2,
            tools_used=["run"], duration_seconds=5.0, cost_usd=0.025,
            llm_call_metrics=metrics,
        )

        assert task.llm_calls == 5
        assert task.base_context == 3000
        cumulatives = [m.cumulative_input for m in task.llm_call_metrics]
        assert cumulatives == [3000, 6500, 10500, 15100, 20300]
        assert 500 <= task.context_growth_avg <= 600

    def test_to_dict_preserves_multi_call_structure(self) -> None:
        """to_dict correctly serializes multi-call metrics."""
        metrics = [
            LLMCallMetrics(call_number=1, input_tokens=1000, output_tokens=100,
                           tool_calls_made=1, cumulative_input=1000, latency_ms=300),
            LLMCallMetrics(call_number=2, input_tokens=1500, output_tokens=150,
                           tool_calls_made=0, cumulative_input=2500, latency_ms=400),
        ]
        task = TaskResult(
            name="test", server="test", model="test", prompt="test", response="test",
            input_tokens=2500, output_tokens=250, llm_calls=2, tool_calls=1,
            tools_used=["tool1"], duration_seconds=1.0, cost_usd=0.01,
            llm_call_metrics=metrics,
        )
        data = task.to_dict()

        assert "llm_call_metrics" in data
        assert len(data["llm_call_metrics"]) == 2
        assert data["llm_call_metrics"][0]["call_number"] == 1
        assert data["llm_call_metrics"][0]["cumulative_input"] == 1000
        assert data["llm_call_metrics"][1]["call_number"] == 2
        assert data["llm_call_metrics"][1]["cumulative_input"] == 2500
