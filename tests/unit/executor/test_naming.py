"""Tests for MCP tool naming utilities."""

import pytest

from ot.executor.naming import (
    canonicalize_name,
    find_canonical_match,
    suggest_similar_names,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


class TestCanonicalizeName:
    """Test name canonicalization."""

    def test_snake_case(self) -> None:
        """Convert snake_case to canonical form."""
        assert canonicalize_name("list_accounts") == "listaccounts"

    def test_kebab_case(self) -> None:
        """Convert kebab-case to canonical form."""
        assert canonicalize_name("list-accounts") == "listaccounts"

    def test_camel_case(self) -> None:
        """Convert camelCase to canonical form."""
        assert canonicalize_name("listAccounts") == "listaccounts"

    def test_pascal_case(self) -> None:
        """Convert PascalCase to canonical form."""
        assert canonicalize_name("ListAccounts") == "listaccounts"

    def test_screaming_snake(self) -> None:
        """Convert SCREAMING_SNAKE_CASE to canonical form."""
        assert canonicalize_name("LIST_ACCOUNTS") == "listaccounts"

    def test_mixed_separators(self) -> None:
        """Handle mixed separators."""
        assert canonicalize_name("list-account_BY-Company") == "listaccountbycompany"

    def test_multiple_underscores(self) -> None:
        """Handle multiple consecutive underscores."""
        assert canonicalize_name("list__accounts") == "listaccounts"

    def test_multiple_hyphens(self) -> None:
        """Handle multiple consecutive hyphens."""
        assert canonicalize_name("list--accounts") == "listaccounts"

    def test_mixed_case_no_separator(self) -> None:
        """Preserve case variations without separators."""
        assert canonicalize_name("listACCOUNTS") == "listaccounts"

    def test_empty_string(self) -> None:
        """Handle empty string."""
        assert canonicalize_name("") == ""

    def test_only_separators(self) -> None:
        """Handle string with only separators."""
        assert canonicalize_name("---___") == ""

    def test_real_mcp_example(self) -> None:
        """Test real MCP server tool name with hyphens and mixed case."""
        assert canonicalize_name("list-organisation-details") == "listorganisationdetails"
        assert canonicalize_name("list_organisation_details") == "listorganisationdetails"
        assert canonicalize_name("listOrganisationDetails") == "listorganisationdetails"
        assert canonicalize_name("ListOrganisationDetails") == "listorganisationdetails"


class TestFindCanonicalMatch:
    """Test fuzzy tool name matching."""

    def test_exact_match_fast_path(self) -> None:
        """Exact match should be returned immediately."""
        available = ["list-accounts", "get-user"]
        assert find_canonical_match("list-accounts", available) == "list-accounts"

    def test_underscore_to_hyphen(self) -> None:
        """Match snake_case to kebab-case."""
        available = ["list-accounts", "get-user"]
        assert find_canonical_match("list_accounts", available) == "list-accounts"

    def test_camel_to_hyphen(self) -> None:
        """Match camelCase to kebab-case."""
        available = ["list-accounts", "get-user"]
        assert find_canonical_match("listAccounts", available) == "list-accounts"

    def test_pascal_to_hyphen(self) -> None:
        """Match PascalCase to kebab-case."""
        available = ["list-accounts", "get-user"]
        assert find_canonical_match("ListAccounts", available) == "list-accounts"

    def test_hyphen_to_underscore(self) -> None:
        """Match kebab-case to snake_case."""
        available = ["list_accounts", "get_user"]
        assert find_canonical_match("list-accounts", available) == "list_accounts"

    def test_hyphen_to_camel(self) -> None:
        """Match kebab-case to camelCase."""
        available = ["listAccounts", "getUser"]
        assert find_canonical_match("list-accounts", available) == "listAccounts"

    def test_no_match(self) -> None:
        """Return None when no match found."""
        available = ["list-accounts", "get-user"]
        assert find_canonical_match("delete-account", available) is None

    def test_empty_available(self) -> None:
        """Handle empty available list."""
        assert find_canonical_match("list_accounts", []) is None

    def test_case_insensitive(self) -> None:
        """Matching is case-insensitive."""
        available = ["list-ACCOUNTS"]
        assert find_canonical_match("LIST_accounts", available) == "list-ACCOUNTS"

    def test_ambiguous_match_error(self) -> None:
        """Raise error when multiple tools match same canonical form."""
        # Two tools that canonicalize to the same form
        available = ["list-accounts", "list_accounts"]
        with pytest.raises(ValueError, match="Ambiguous tool name.*matches multiple tools"):
            find_canonical_match("listAccounts", available)

    def test_ambiguous_match_includes_suggestions(self) -> None:
        """Error message includes the ambiguous matches."""
        available = ["get-user", "get_user"]
        with pytest.raises(ValueError, match=r"\['get-user', 'get_user'\]"):
            find_canonical_match("getUser", available)

    def test_real_mcp_tools(self) -> None:
        """Test with real MCP server tool names using hyphenated naming."""
        available = [
            "list-organisation-details",
            "list-accounts",
            "list-aged-payables-by-contact",
            "list-invoices",
        ]

        # All these should match list-organisation-details
        assert find_canonical_match("list_organisation_details", available) == "list-organisation-details"
        assert find_canonical_match("listOrganisationDetails", available) == "list-organisation-details"
        assert find_canonical_match("ListOrganisationDetails", available) == "list-organisation-details"

        # Match other tools
        assert find_canonical_match("list_accounts", available) == "list-accounts"
        assert find_canonical_match("listInvoices", available) == "list-invoices"


class TestSuggestSimilarNames:
    """Test similar name suggestions."""

    def test_starts_with_match(self) -> None:
        """Suggest names that start with the accessor."""
        available = ["list-accounts", "list-items", "get-account"]
        suggestions = suggest_similar_names("list_acc", available)
        # list-accounts starts with "listacc" (canonical "list_acc")
        assert "list-accounts" in suggestions
        # list-items also starts with "list" but not "listacc", so won't match

    def test_contains_match(self) -> None:
        """Suggest names that contain the accessor."""
        available = ["get-user-account", "list-accounts", "account-details", "delete-item"]
        suggestions = suggest_similar_names("account", available)
        # All of these contain "account" in canonical form
        assert "list-accounts" in suggestions
        assert "get-user-account" in suggestions
        assert "account-details" in suggestions
        # delete-item doesn't contain "account"
        assert "delete-item" not in suggestions

    def test_starts_with_preferred_over_contains(self) -> None:
        """Names starting with accessor should come first."""
        available = ["account-details", "get-account", "list-accounts"]
        suggestions = suggest_similar_names("account", available)
        # account-details starts with "account" (canonical)
        assert suggestions[0] == "account-details"

    def test_max_suggestions_limit(self) -> None:
        """Respect max_suggestions parameter."""
        available = [f"list-item-{i}" for i in range(10)]
        suggestions = suggest_similar_names("list", available, max_suggestions=3)
        assert len(suggestions) == 3

    def test_no_similar_names(self) -> None:
        """Return empty list when no similar names found."""
        available = ["get-user", "delete-item"]
        suggestions = suggest_similar_names("xyz", available)
        assert suggestions == []

    def test_case_insensitive_matching(self) -> None:
        """Suggestions are case-insensitive."""
        available = ["LIST-ACCOUNTS", "list-items"]
        suggestions = suggest_similar_names("list_acc", available)
        assert "LIST-ACCOUNTS" in suggestions

    def test_separator_agnostic(self) -> None:
        """Suggestions ignore separators."""
        available = ["list-accounts", "list_items", "listUsers"]
        suggestions = suggest_similar_names("list_acc", available)
        assert "list-accounts" in suggestions

    def test_real_mcp_typo(self) -> None:
        """Test with realistic typo in an MCP tool name."""
        available = [
            "list-organisation-details",
            "list-accounts",
            "list-aged-payables-by-contact",
            "list-invoices",
        ]

        # Typo: "organis" instead of full name
        suggestions = suggest_similar_names("list_organis", available)
        assert "list-organisation-details" in suggestions

        # Typo: "invoice" instead of "invoices"
        suggestions = suggest_similar_names("listInvoice", available)
        assert "list-invoices" in suggestions
