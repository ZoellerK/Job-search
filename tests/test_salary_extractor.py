"""Tests for salary_extractor.py"""
import pytest

from salary_extractor import extract_salary


class TestRangePatterns:
    def test_dollar_range_with_commas(self):
        text = "The salary for this role is $60,000 - $80,000 annually."
        assert extract_salary(text) == "$60,000 - $80,000 annually"

    def test_dollar_range_k_notation(self):
        text = "Compensation: $75k-$100k"
        assert extract_salary(text) == "$75k-$100k"

    def test_dollar_range_with_to(self):
        text = "Pay range is $80,000 to $100,000 per year."
        assert extract_salary(text) == "$80,000 to $100,000 per year"

    def test_dollar_range_one_dollar_sign(self):
        text = "Salary range: $90,000 - 120,000"
        assert extract_salary(text) == "$90,000 - 120,000"

    def test_en_dash_separator(self):
        text = "The range is $55,000\u2013$70,000/year."
        assert extract_salary(text) == "$55,000\u2013$70,000/year"


class TestSingleValuePatterns:
    def test_hourly_rate(self):
        text = "This is a part-time role paying $45/hour."
        assert extract_salary(text) == "$45/hour"

    def test_annual_salary(self):
        text = "Starting at $120,000/year with benefits."
        assert extract_salary(text) == "$120,000/year"

    def test_salary_keyword_prefix(self):
        text = "Salary: $90,000"
        assert extract_salary(text) == "$90,000"

    def test_compensation_keyword(self):
        text = "Compensation: $75k"
        assert extract_salary(text) == "$75k"


class TestRejections:
    def test_returns_none_for_empty(self):
        assert extract_salary("") is None
        assert extract_salary(None) is None

    def test_no_salary_in_text(self):
        text = "We are looking for a Senior Engineer to join our team."
        assert extract_salary(text) is None

    def test_rejects_budget_context(self):
        text = "The organization has a budget of $5,000,000 - $10,000,000 annually."
        assert extract_salary(text) is None

    def test_rejects_grant_context(self):
        text = "We distribute grant awards of $50,000 - $100,000 per year."
        assert extract_salary(text) is None


class TestEdgeCases:
    def test_salary_buried_in_long_description(self):
        text = (
            "About the role: We are seeking a Program Manager to oversee our "
            "international operations. " * 20
            + "The salary range for this position is $85,000 - $110,000."
        )
        assert extract_salary(text) == "$85,000 - $110,000"

    def test_k_with_decimal(self):
        text = "Range: $120.5k-$150k"
        result = extract_salary(text)
        assert result is not None
        assert "120.5k" in result

    def test_usd_prefix(self):
        text = "Compensation is USD 80,000-100,000 annually."
        assert extract_salary(text) == "USD 80,000-100,000 annually"
