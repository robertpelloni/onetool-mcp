"""Unit tests for context7 tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestContext7Pack:
    """Test context7 pack structure."""

    def test_pack_name(self):
        from otdev.tools import context7

        assert context7.pack == "context7"

    def test_has_all_exports(self):
        from otdev.tools import context7

        # Context7 should export search and doc functions
        assert hasattr(context7, "__all__")
        expected = {"search", "doc"}
        assert expected.issubset(set(context7.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import context7

        for name in context7.__all__:
            func = getattr(context7, name)
            assert callable(func), f"{name} should be callable"

    def test_follow_redirects_enabled(self):
        """HTTP client must follow redirects to handle Context7 API 301s."""
        from otdev.tools.context7 import _create_http_client

        client = _create_http_client()
        assert client.follow_redirects is True


@pytest.mark.unit
@pytest.mark.tools
class TestDocQueryRequired:
    """Test that doc() requires the query argument."""

    def test_doc_requires_query(self):
        from otdev.tools import context7

        with pytest.raises(TypeError):
            context7.doc(library_id="/fastapi/fastapi")  # type: ignore[call-arg]

    def test_doc_empty_query_returns_error(self):
        from otdev.tools import context7

        result = context7.doc(library_id="/fastapi/fastapi", query="")
        assert "query is required" in result

    def test_doc_whitespace_query_returns_error(self):
        from otdev.tools import context7

        result = context7.doc(library_id="/fastapi/fastapi", query="   ")
        assert "query is required" in result

    def test_doc_query_included_in_params(self, monkeypatch):
        from otdev.tools import context7

        captured: list[dict] = []

        def fake_request(url, params=None, timeout=None):
            captured.append(params or {})
            return True, "some docs"

        monkeypatch.setattr(context7, "_resolve_library_id", lambda x: (x, False, True))
        monkeypatch.setattr(context7, "_make_request", fake_request)

        context7.doc(library_id="/fastapi/fastapi", query="how to use dependencies")
        assert captured[0].get("query") == "how to use dependencies"


@pytest.mark.unit
@pytest.mark.tools
class TestHasTitleOverlap:
    """Test _has_title_overlap helper used to reject wrong-library matches."""

    def setup_method(self):
        from otdev.tools.context7 import _has_title_overlap

        self.fn = _has_title_overlap

    def test_exact_match(self):
        assert self.fn("react", "React") is True

    def test_shorthand_strips_punctuation(self):
        # "nextjs" should match "Next.js" after stripping punctuation
        assert self.fn("nextjs", "Next.js") is True

    def test_query_in_title(self):
        assert self.fn("fastapi", "FastAPI") is True

    def test_title_in_query(self):
        assert self.fn("react-router-dom", "React Router") is True

    def test_no_overlap_returns_false(self):
        assert self.fn("nonexistent-library-xyz-404", "paperless-ai") is False

    def test_no_overlap_unrelated_names(self):
        assert self.fn("webpack", "paperless-ai") is False

    def test_empty_title_returns_false(self):
        assert self.fn("react", "") is False

    def test_empty_query_returns_false(self):
        assert self.fn("", "React") is False


@pytest.mark.unit
@pytest.mark.tools
class TestPickBestLibrary:
    """Test _pick_best_library rejects results with no title overlap."""

    def setup_method(self):
        from otdev.tools.context7 import _pick_best_library

        self.fn = _pick_best_library

    def _make_result(self, id: str, title: str, **kwargs) -> dict:
        return {
            "id": id,
            "title": title,
            "vip": kwargs.get("vip", False),
            "verified": kwargs.get("verified", False),
            "trustScore": kwargs.get("trustScore", 5),
            "totalTokens": kwargs.get("totalTokens", 50000),
            "stars": kwargs.get("stars", 0),
            "benchmarkScore": kwargs.get("benchmarkScore", 50),
        }

    def test_returns_best_matching_library(self):
        data = {
            "results": [
                self._make_result("/vercel/next.js", "Next.js", vip=True, verified=True, trustScore=10),
                self._make_result("/some/other", "SomeThing", vip=False),
            ]
        }
        result = self.fn(data, "nextjs")
        assert result == "/vercel/next.js"

    def test_returns_none_for_no_overlap(self):
        """A query with no title overlap should return None, not a wrong library."""
        data = {
            "results": [
                self._make_result(
                    "/clusterzx/paperless-ai",
                    "paperless-ai",
                    vip=True,
                    verified=True,
                    trustScore=10,
                    benchmarkScore=90,
                ),
            ]
        }
        result = self.fn(data, "nonexistent-library-xyz-404")
        assert result is None

    def test_returns_none_for_empty_results(self):
        assert self.fn({"results": []}, "react") is None

    def test_returns_none_for_none_input(self):
        assert self.fn(None, "react") is None


@pytest.mark.unit
@pytest.mark.tools
class TestSearchStrFormat:
    """Test search() output_format='str' returns formatted markdown list."""

    def _make_search_result(self):
        return {
            "results": [
                {
                    "id": "/vercel/next.js",
                    "title": "Next.js",
                    "description": "The React framework for production.",
                },
                {
                    "id": "reactjs/react.dev",  # no leading slash
                    "title": "React",
                    "description": "",
                },
            ]
        }

    def test_str_format_is_markdown_list(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (True, self._make_search_result()),
        )

        result = context7.search(query="react framework", library_name="react")

        # "React" matches library_name="react", so it appears
        assert "**React**" in result
        # Leading slash added for IDs missing it
        assert "`/reactjs/react.dev`" in result
        # "Next.js" doesn't overlap with "react", so it's filtered out
        assert "**Next.js**" not in result
        # Should NOT be Python repr
        assert result.startswith("{") is False

    def test_str_format_no_results(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (True, {"results": []}),
        )

        result = context7.search(query="nothing", library_name="nothing")
        assert result == "No libraries found."

    def test_dict_format_returns_dict(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (True, self._make_search_result()),
        )

        result = context7.search(
            query="react", library_name="react", output_format="dict"
        )
        assert isinstance(result, dict)
        assert "results" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSearchQueryRequired:
    """Test that search() requires a non-empty query."""

    def test_search_empty_query_returns_error(self):
        from otdev.tools import context7

        result = context7.search(query="", library_name="react")
        assert "query is required" in result

    def test_search_whitespace_query_returns_error(self):
        from otdev.tools import context7

        result = context7.search(query="   ", library_name="react")
        assert "query is required" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSearchNoMatchWarning:
    """Test that search() warns when results don't match library_name."""

    def _make_unrelated_results(self):
        return {
            "results": [
                {"id": "/foo/bar", "title": "FooBar", "description": "Unrelated lib"},
                {"id": "/baz/qux", "title": "BazQux", "description": "Another one"},
            ]
        }

    def test_no_match_shows_warning(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (True, self._make_unrelated_results()),
        )

        result = context7.search(
            query="how to use", library_name="nonexistent-xyz-12345"
        )
        assert "No libraries matching" in result
        assert "nonexistent-xyz-12345" in result
        # Results are still shown after the warning
        assert "FooBar" in result

    def test_matching_results_no_warning(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (True, {"results": [
                {"id": "/reactjs/react.dev", "title": "React", "description": "A JS lib"},
            ]}),
        )

        result = context7.search(query="hooks", library_name="react")
        assert "No libraries matching" not in result
        assert "**React**" in result


@pytest.mark.unit
@pytest.mark.tools
class TestDocFriendly404:
    """Test that doc() returns user-friendly message on 404."""

    def test_404_returns_friendly_message(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_resolve_library_id",
            lambda x: ("/invalid/lib", False, True),
        )
        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (False, "HTTP error (404): HTTPStatusError"),
        )

        result = context7.doc(library_id="invalid/lib", query="how to install")
        assert "was not found in Context7" in result
        assert "context7.search" in result

    def test_non_404_error_unchanged(self, monkeypatch):
        from otdev.tools import context7

        monkeypatch.setattr(
            context7,
            "_resolve_library_id",
            lambda x: ("/some/lib", False, True),
        )
        monkeypatch.setattr(
            context7,
            "_make_request",
            lambda *a, **kw: (False, "HTTP error (500): Internal Server Error"),
        )

        result = context7.doc(library_id="some/lib", query="how to install")
        assert "500" in result
        assert "was not found" not in result
