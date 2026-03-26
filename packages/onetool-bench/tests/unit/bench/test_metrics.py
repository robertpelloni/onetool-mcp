"""Unit tests for benchmark metrics module."""

import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from bench.harness.csv_writer import write_results_csv
from bench.harness.metrics import LLMCallMetrics, ScenarioResult, TaskResult, get_openrouter_pricing
from bench.harness.runner import split_prompts

# =============================================================================
# LLMCallMetrics tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestLLMCallMetrics:
    """Tests for LLMCallMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Basic creation of LLMCallMetrics."""
        metrics = LLMCallMetrics(
            call_number=1,
            input_tokens=1000,
            output_tokens=200,
            tool_calls_made=2,
            cumulative_input=1000,
            latency_ms=500,
        )
        assert metrics.call_number == 1
        assert metrics.input_tokens == 1000
        assert metrics.output_tokens == 200
        assert metrics.tool_calls_made == 2
        assert metrics.cumulative_input == 1000
        assert metrics.latency_ms == 500

    def test_metrics_cumulative_tracking(self) -> None:
        """Verify cumulative_input tracks across calls."""
        call1 = LLMCallMetrics(
            call_number=1,
            input_tokens=1000,
            output_tokens=100,
            tool_calls_made=1,
            cumulative_input=1000,
            latency_ms=300,
        )
        call2 = LLMCallMetrics(
            call_number=2,
            input_tokens=1500,
            output_tokens=150,
            tool_calls_made=1,
            cumulative_input=2500,  # 1000 + 1500
            latency_ms=400,
        )
        assert call2.cumulative_input == call1.cumulative_input + call2.input_tokens


# =============================================================================
# TaskResult helper methods tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestTaskResultHelpers:
    """Tests for TaskResult base_context and context_growth_avg helpers."""

    def _make_task_result(
        self, llm_call_metrics: list[LLMCallMetrics] | None = None
    ) -> TaskResult:
        """Helper to create a TaskResult for testing."""
        return TaskResult(
            name="test_task",
            server="test_server",
            model="test_model",
            prompt="test prompt",
            response="test response",
            input_tokens=100,
            output_tokens=50,
            llm_calls=1,
            tool_calls=1,
            tools_used=["tool1"],
            duration_seconds=1.5,
            cost_usd=0.01,
            llm_call_metrics=llm_call_metrics or [],
        )

    def test_base_context_empty_metrics(self) -> None:
        """base_context returns 0 when no metrics."""
        result = self._make_task_result()
        assert result.base_context == 0

    def test_base_context_with_metrics(self) -> None:
        """base_context returns first call's input tokens."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=1500,
                output_tokens=150,
                tool_calls_made=0,
                cumulative_input=2500,
                latency_ms=400,
            ),
        ]
        result = self._make_task_result(metrics)
        assert result.base_context == 1000

    def test_context_growth_avg_empty_metrics(self) -> None:
        """context_growth_avg returns 0 when no metrics."""
        result = self._make_task_result()
        assert result.context_growth_avg == 0.0

    def test_context_growth_avg_single_call(self) -> None:
        """context_growth_avg returns 0 for single call."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
        ]
        result = self._make_task_result(metrics)
        assert result.context_growth_avg == 0.0

    def test_context_growth_avg_multiple_calls(self) -> None:
        """context_growth_avg calculates average growth correctly."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=1500,
                output_tokens=150,
                tool_calls_made=1,
                cumulative_input=2500,
                latency_ms=400,
            ),
            LLMCallMetrics(
                call_number=3,
                input_tokens=2000,
                output_tokens=200,
                tool_calls_made=0,
                cumulative_input=4500,
                latency_ms=500,
            ),
        ]
        result = self._make_task_result(metrics)
        # Growth: call1->call2 = 500, call2->call3 = 500
        # Average = (500 + 500) / 2 = 500
        assert result.context_growth_avg == 500.0

    def test_to_dict_includes_llm_call_metrics(self) -> None:
        """to_dict includes llm_call_metrics when present."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
        ]
        result = self._make_task_result(metrics)
        data = result.to_dict()
        assert "llm_call_metrics" in data
        assert len(data["llm_call_metrics"]) == 1
        assert data["llm_call_metrics"][0]["call_number"] == 1
        assert data["llm_call_metrics"][0]["input_tokens"] == 1000

    def test_to_dict_omits_empty_metrics(self) -> None:
        """to_dict omits llm_call_metrics when empty."""
        result = self._make_task_result()
        data = result.to_dict()
        assert "llm_call_metrics" not in data


# =============================================================================
# split_prompts tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestSplitPrompts:
    """Tests for split_prompts helper function."""

    def test_single_prompt_no_delimiter(self) -> None:
        """Single prompt without delimiter returns as-is."""
        result = split_prompts("Check npm version for express")
        assert result == ["Check npm version for express"]

    def test_empty_prompt(self) -> None:
        """Empty prompt returns list with single empty string."""
        result = split_prompts("")
        assert result == [""]

    def test_multiple_prompts(self) -> None:
        """Multiple prompts are split correctly."""
        prompt = """First prompt here
---PROMPT---
Second prompt here
---PROMPT---
Third prompt here"""
        result = split_prompts(prompt)
        assert len(result) == 3
        assert result[0] == "First prompt here"
        assert result[1] == "Second prompt here"
        assert result[2] == "Third prompt here"

    def test_whitespace_trimmed(self) -> None:
        """Whitespace is trimmed from each prompt."""
        prompt = """  First prompt
---PROMPT---
  Second prompt  """
        result = split_prompts(prompt)
        assert result[0] == "First prompt"
        assert result[1] == "Second prompt"

    def test_empty_segments_skipped(self) -> None:
        """Empty segments between delimiters are skipped."""
        prompt = """First prompt
---PROMPT---

---PROMPT---
Second prompt"""
        result = split_prompts(prompt)
        assert len(result) == 2
        assert result[0] == "First prompt"
        assert result[1] == "Second prompt"

    def test_multiline_prompts(self) -> None:
        """Multi-line prompts within segments are preserved."""
        prompt = """>>>
```python
npm = check_npm()
```
Return versions.
---PROMPT---
>>>
```python
other = check_other()
```
Return values."""
        result = split_prompts(prompt)
        assert len(result) == 2
        assert "```python" in result[0]
        assert "npm = check_npm()" in result[0]
        assert "other = check_other()" in result[1]


# =============================================================================
# Context metrics + CSV integration tests (moved from integration/)
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestContextMetricsUnit:
    """Unit tests for context metrics and CSV export."""

    def test_task_result_with_metrics_to_csv(self, tmp_path: Path) -> None:
        """Verify CSV export includes base_context and context_growth_avg."""
        onetool_metrics = [
            LLMCallMetrics(call_number=1, input_tokens=5000, output_tokens=500,
                           tool_calls_made=1, cumulative_input=5000, latency_ms=1200),
            LLMCallMetrics(call_number=2, input_tokens=6000, output_tokens=200,
                           tool_calls_made=0, cumulative_input=11000, latency_ms=800),
        ]
        mcp_metrics = [
            LLMCallMetrics(call_number=1, input_tokens=5000, output_tokens=300,
                           tool_calls_made=1, cumulative_input=5000, latency_ms=600),
            LLMCallMetrics(call_number=2, input_tokens=5800, output_tokens=250,
                           tool_calls_made=1, cumulative_input=10800, latency_ms=500),
            LLMCallMetrics(call_number=3, input_tokens=6500, output_tokens=200,
                           tool_calls_made=1, cumulative_input=17300, latency_ms=400),
            LLMCallMetrics(call_number=4, input_tokens=7200, output_tokens=150,
                           tool_calls_made=0, cumulative_input=24500, latency_ms=350),
        ]
        onetool_task = TaskResult(
            name="version-check-onetool", server="onetool", model="test-model",
            prompt="Check npm versions", response="express: 5.0.0",
            input_tokens=11000, output_tokens=700, llm_calls=2, tool_calls=1,
            tools_used=["run"], duration_seconds=3.5, cost_usd=0.015,
            llm_call_metrics=onetool_metrics,
        )
        mcp_task = TaskResult(
            name="version-check-mcp", server="multiple-mcp", model="test-model",
            prompt="Check npm versions", response="express: 5.0.0",
            input_tokens=24500, output_tokens=900, llm_calls=4, tool_calls=3,
            tools_used=["check_npm", "check_pypi", "check_go"],
            duration_seconds=8.2, cost_usd=0.035, llm_call_metrics=mcp_metrics,
        )
        scenario = ScenarioResult(name="compare", model="test-model",
                                  tasks=[onetool_task, mcp_task])
        csv_path = write_results_csv([scenario], output_dir=tmp_path)

        with csv_path.open() as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2
        assert rows[0]["base_context"] == "5000"
        assert int(rows[0]["llm_calls"]) == 2
        assert rows[1]["base_context"] == "5000"
        assert int(rows[1]["llm_calls"]) == 4
        assert 900 <= float(rows[0]["context_growth_avg"]) <= 1100
        assert 600 <= float(rows[1]["context_growth_avg"]) <= 850

    def test_context_efficiency_calculation(self) -> None:
        """base_context and context_growth_avg are calculated correctly."""
        metrics = [
            LLMCallMetrics(call_number=1, input_tokens=1000, output_tokens=100,
                           tool_calls_made=1, cumulative_input=1000, latency_ms=200),
            LLMCallMetrics(call_number=2, input_tokens=1200, output_tokens=100,
                           tool_calls_made=1, cumulative_input=2200, latency_ms=200),
            LLMCallMetrics(call_number=3, input_tokens=1400, output_tokens=100,
                           tool_calls_made=0, cumulative_input=3600, latency_ms=200),
        ]
        task = TaskResult(
            name="test", server="test", model="test", prompt="test", response="test",
            input_tokens=3600, output_tokens=300, llm_calls=3, tool_calls=2,
            tools_used=["tool1"], duration_seconds=1.0, cost_usd=0.01,
            llm_call_metrics=metrics,
        )
        assert task.base_context == 1000
        # average of (1200-1000, 1400-1200) = 200
        assert task.context_growth_avg == 200.0


# =============================================================================
# Pricing cache tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestPricing:
    """Tests for get_openrouter_pricing caching behaviour."""

    def test_failed_fetch_does_not_poison_cache(self) -> None:
        """A transient fetch failure leaves the cache as None so the next call retries."""
        import bench.harness.metrics as m

        original = m._openrouter_pricing
        m._openrouter_pricing = None
        try:
            with patch("bench.harness.metrics.httpx.get", side_effect=Exception("network error")):
                result = get_openrouter_pricing()
            assert result == {}
            assert m._openrouter_pricing is None  # cache not poisoned
        finally:
            m._openrouter_pricing = original

    def test_successful_fetch_populates_cache(self) -> None:
        """A successful fetch populates and returns the cache."""
        import bench.harness.metrics as m

        original = m._openrouter_pricing
        m._openrouter_pricing = None
        try:
            mock_response = patch("bench.harness.metrics.httpx.get")
            with mock_response as mock_get:
                mock_get.return_value.raise_for_status.return_value = None
                mock_get.return_value.json.return_value = {
                    "data": [
                        {"id": "test/model", "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
                    ]
                }
                result = get_openrouter_pricing()
            assert "test/model" in result
            assert m._openrouter_pricing is not None
        finally:
            m._openrouter_pricing = original
