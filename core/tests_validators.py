"""
Tests for input validation utilities.
"""

import uuid

import pytest
from rest_framework.exceptions import ValidationError

from .validators import (
    COUPON_CODE_PATTERN,
    DISPLAY_NAME_PATTERN,
    LOCATION_PATTERN,
    MAX_PAGE_SIZE,
    MAX_SEARCH_QUERY_LENGTH,
    MAX_TEXT_FIELD_LENGTH,
    TAG_NAME_PATTERN,
    UUID_PATTERN,
    validate_coupon_code,
    validate_display_name,
    validate_location,
    validate_pagination_params,
    validate_search_query,
    validate_tag_name,
    validate_text_length,
    validate_uuid,
)


class TestValidateUUID:
    """Tests for validate_uuid function."""

    def test_valid_uuid_string(self):
        valid = "12345678-1234-1234-1234-123456789abc"
        result = validate_uuid(valid)
        assert isinstance(result, uuid.UUID)

    def test_valid_uuid_object(self):
        uid = uuid.uuid4()
        result = validate_uuid(uid)
        assert result == uid

    def test_valid_uuid_uppercase(self):
        valid = "12345678-1234-1234-1234-123456789ABC"
        result = validate_uuid(valid)
        assert isinstance(result, uuid.UUID)

    def test_invalid_uuid_string(self):
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("not-a-uuid")

    def test_empty_string(self):
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("")

    def test_integer_input(self):
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid(123)

    def test_none_input(self):
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid(None)

    def test_partial_uuid(self):
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("12345678-1234-1234")

    def test_uuid_without_dashes(self):
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("123456781234123412341234567890ab")


class TestValidatePaginationParams:
    """Tests for validate_pagination_params function."""

    def test_valid_params(self):
        page, size = validate_pagination_params(1, 20)
        assert page == 1
        assert size == 20

    def test_default_values(self):
        page, size = validate_pagination_params(None, None)
        assert page == 1
        assert size == 20

    def test_string_params(self):
        page, size = validate_pagination_params("2", "30")
        assert page == 2
        assert size == 30

    def test_max_page_size(self):
        page, size = validate_pagination_params(1, MAX_PAGE_SIZE)
        assert size == MAX_PAGE_SIZE

    def test_over_max_page_size(self):
        with pytest.raises(ValidationError, match="Page size"):
            validate_pagination_params(1, MAX_PAGE_SIZE + 1)

    def test_zero_page_defaults_to_one(self):
        # 0 is falsy, so the code defaults it to page=1
        page, size = validate_pagination_params(0, 20)
        assert page == 1

    def test_negative_page(self):
        with pytest.raises(ValidationError, match="Page must be"):
            validate_pagination_params(-1, 20)

    def test_zero_page_size_defaults_to_20(self):
        # 0 is falsy, so the code defaults it to page_size=20
        page, size = validate_pagination_params(1, 0)
        assert size == 20

    def test_negative_page_size(self):
        with pytest.raises(ValidationError, match="Page size"):
            validate_pagination_params(1, -5)

    def test_invalid_string_page(self):
        with pytest.raises(ValidationError, match="Invalid pagination"):
            validate_pagination_params("abc", 20)

    def test_invalid_string_size(self):
        with pytest.raises(ValidationError, match="Invalid pagination"):
            validate_pagination_params(1, "xyz")


class TestValidateSearchQuery:
    """Tests for validate_search_query function."""

    def test_valid_query(self):
        result = validate_search_query("hello world")
        assert result == "hello world"

    def test_empty_query(self):
        result = validate_search_query("")
        assert result == ""

    def test_none_query(self):
        result = validate_search_query(None)
        assert result == ""

    def test_non_string_query(self):
        result = validate_search_query(123)
        assert result == ""

    def test_strips_html_tags(self):
        result = validate_search_query('<script>alert("xss")</script>test')
        assert "<script>" not in result
        assert "test" in result

    def test_truncates_long_query(self):
        long_query = "a" * 300
        result = validate_search_query(long_query)
        assert len(result) == MAX_SEARCH_QUERY_LENGTH

    def test_strips_whitespace(self):
        result = validate_search_query("  hello  ")
        assert result == "hello"

    def test_exact_max_length(self):
        query = "a" * MAX_SEARCH_QUERY_LENGTH
        result = validate_search_query(query)
        assert len(result) == MAX_SEARCH_QUERY_LENGTH


class TestValidateDisplayName:
    """Tests for validate_display_name function."""

    def test_valid_name(self):
        result = validate_display_name("John Doe")
        assert result == "John Doe"

    def test_name_with_accents(self):
        result = validate_display_name("José García")
        assert result == "José García"

    def test_name_with_apostrophe(self):
        result = validate_display_name("O'Brien")
        assert "O'Brien" in result

    def test_name_with_hyphen(self):
        result = validate_display_name("Mary-Jane")
        assert result == "Mary-Jane"

    def test_empty_name_allowed(self):
        result = validate_display_name("")
        assert result == ""

    def test_strips_html(self):
        result = validate_display_name("<script>evil</script>John")
        assert "<script>" not in result

    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_display_name("John@Doe!")

    def test_name_with_numbers(self):
        result = validate_display_name("User123")
        assert result == "User123"


class TestValidateLocation:
    """Tests for validate_location function."""

    def test_valid_location(self):
        result = validate_location("Paris, France")
        assert result == "Paris, France"

    def test_location_with_parentheses(self):
        result = validate_location("New York (NY)")
        assert result == "New York (NY)"

    def test_empty_location(self):
        result = validate_location("")
        assert result == ""

    def test_strips_html(self):
        result = validate_location("<b>Paris</b>")
        assert "<b>" not in result

    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_location("Paris; DROP TABLE")


class TestValidateCouponCode:
    """Tests for validate_coupon_code function."""

    def test_valid_coupon(self):
        result = validate_coupon_code("SUMMER2024")
        assert result == "SUMMER2024"

    def test_coupon_with_hyphen(self):
        result = validate_coupon_code("SAVE-50")
        assert result == "SAVE-50"

    def test_coupon_with_underscore(self):
        result = validate_coupon_code("NEW_USER")
        assert result == "NEW_USER"

    def test_empty_coupon(self):
        result = validate_coupon_code("")
        assert result == ""

    def test_invalid_coupon(self):
        with pytest.raises(ValidationError, match="Coupon code"):
            validate_coupon_code("SAVE 50%!")


class TestValidateTagName:
    """Tests for validate_tag_name function."""

    def test_valid_tag(self):
        result = validate_tag_name("fitness")
        assert result == "fitness"

    def test_tag_with_space(self):
        result = validate_tag_name("personal growth")
        assert result == "personal growth"

    def test_tag_with_accents(self):
        result = validate_tag_name("éducation")
        assert result == "éducation"

    def test_empty_tag_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_tag_name("")

    def test_invalid_tag_characters(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_tag_name("tag@#$")


class TestValidateTextLength:
    """Tests for validate_text_length function."""

    def test_valid_text(self):
        result = validate_text_length("Hello world")
        assert result == "Hello world"

    def test_max_length_text(self):
        text = "a" * MAX_TEXT_FIELD_LENGTH
        result = validate_text_length(text)
        assert len(result) == MAX_TEXT_FIELD_LENGTH

    def test_over_max_length(self):
        text = "a" * (MAX_TEXT_FIELD_LENGTH + 1)
        with pytest.raises(ValidationError, match="at most"):
            validate_text_length(text)

    def test_custom_max_length(self):
        with pytest.raises(ValidationError, match="at most 10"):
            validate_text_length("a" * 11, max_length=10, field_name="Name")

    def test_strips_html(self):
        result = validate_text_length("<b>Hello</b>")
        assert "<b>" not in result
        assert "Hello" in result


class TestRegexPatterns:
    """Test regex patterns directly for edge cases."""

    def test_uuid_pattern_valid(self):
        assert UUID_PATTERN.match("12345678-1234-1234-1234-123456789abc")

    def test_uuid_pattern_invalid(self):
        assert not UUID_PATTERN.match("12345678-1234-1234-1234")

    def test_display_name_100_chars(self):
        name = "A" * 100
        assert DISPLAY_NAME_PATTERN.match(name)

    def test_display_name_101_chars_fails(self):
        name = "A" * 101
        assert not DISPLAY_NAME_PATTERN.match(name)

    def test_location_200_chars(self):
        loc = "A" * 200
        assert LOCATION_PATTERN.match(loc)

    def test_coupon_50_chars(self):
        code = "A" * 50
        assert COUPON_CODE_PATTERN.match(code)

    def test_coupon_51_chars_fails(self):
        code = "A" * 51
        assert not COUPON_CODE_PATTERN.match(code)

    def test_tag_name_50_chars(self):
        tag = "A" * 50
        assert TAG_NAME_PATTERN.match(tag)
