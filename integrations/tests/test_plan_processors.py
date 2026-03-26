"""Tests for plan_processors.py — category detection + processor loading."""
import pytest
from integrations.plan_processors import (
    get_processor, detect_category_from_text, detect_category_with_ambiguity,
    PROCESSORS, KEYWORD_MAP, CATEGORY_DISPLAY_NAMES, BasePlanProcessor,
)


class TestProcessorRegistry:
    """Test that all processors are properly registered."""

    def test_all_display_names_have_processors(self):
        for cat in CATEGORY_DISPLAY_NAMES:
            p = get_processor(cat)
            assert p is not None
            assert not isinstance(p, BasePlanProcessor) or cat == 'other'

    def test_all_processors_have_domain_rules(self):
        for cat in CATEGORY_DISPLAY_NAMES:
            if cat == 'other':
                continue
            p = get_processor(cat)
            assert p.domain_rules, f"{cat} has no domain_rules"

    def test_all_processors_have_calibration_hints(self):
        for cat in CATEGORY_DISPLAY_NAMES:
            if cat == 'other':
                continue
            p = get_processor(cat)
            assert p.extra_calibration_hints, f"{cat} has no calibration_hints"

    def test_all_keyword_maps_have_display_names(self):
        for cat in KEYWORD_MAP:
            assert cat in CATEGORY_DISPLAY_NAMES, f"{cat} in KEYWORD_MAP but not in DISPLAY_NAMES"

    def test_processor_count(self):
        assert len(CATEGORY_DISPLAY_NAMES) >= 85


class TestCategoryDetection:
    """Test keyword-based category detection."""

    @pytest.mark.parametrize("title,expected", [
        ("Run a marathon", "health"),
        ("Courir un marathon", "health"),
        ("Learn Python programming", "tech"),
        ("Apprendre le piano", "creative"),
        ("Start a startup", "startup"),
        ("Perdre 10 kilos", "health"),
        ("Invest in stocks", "investing"),
        ("Write a novel", "writing"),
        ("Plan my wedding", "wedding"),
        ("Get my driving license", "driving"),
        ("Quit smoking", "sobriety"),
        ("Méditer chaque jour", "spirituality"),
        ("Build a mobile app", "app_dev"),
        ("Rénover ma cuisine", "home_renovation"),
        ("Adopt a dog", "pets"),
    ])
    def test_detection(self, title, expected):
        result = detect_category_from_text(title, "")
        assert result == expected, f"'{title}' detected as '{result}', expected '{expected}'"

    def test_unknown_returns_other(self):
        result = detect_category_from_text("xyzzy", "")
        assert result == "other"

    def test_get_processor_unknown_returns_base(self):
        p = get_processor("nonexistent")
        assert isinstance(p, BasePlanProcessor)

    def test_get_processor_none_returns_base(self):
        p = get_processor(None)
        assert isinstance(p, BasePlanProcessor)


class TestProcessorOutput:
    """Test processor methods return valid content."""

    def test_get_planning_rules_not_empty(self):
        p = get_processor("health")
        rules = p.get_planning_rules()
        assert "DOMAIN-SPECIFIC RULES" in rules

    def test_get_calibration_hints_not_empty(self):
        p = get_processor("finance")
        hints = p.get_calibration_hints()
        assert "CALIBRATION" in hints

    def test_base_processor_returns_empty(self):
        p = BasePlanProcessor()
        assert p.get_planning_rules() == ""
        assert p.get_calibration_hints() == ""
