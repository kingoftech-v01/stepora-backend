"""
Tests for integrations.plan_processors — processors, detection, and language.

No database needed; all logic is pure Python.
"""


from integrations.plan_processors import (
    CATEGORY_DISPLAY_NAMES,
    DEFAULT_PROCESSOR,
    KEYWORD_MAP,
    PROCESSORS,
    BasePlanProcessor,
    CareerBusinessProcessor,
    CreativeArtsProcessor,
    EducationProcessor,
    FinanceProcessor,
    HealthFitnessProcessor,
    LanguageLearningProcessor,
    PersonalDevelopmentProcessor,
    RelationshipsProcessor,
    TechSkillsProcessor,
    TravelAdventureProcessor,
    _score_categories,
    detect_category_from_text,
    detect_category_with_ambiguity,
    detect_language,
    get_processor,
)

# ===================================================================
# get_processor()
# ===================================================================

class TestGetProcessor:

    def test_health(self):
        p = get_processor("health")
        assert isinstance(p, HealthFitnessProcessor)

    def test_fitness_alias(self):
        p = get_processor("fitness")
        assert isinstance(p, HealthFitnessProcessor)

    def test_finance(self):
        assert isinstance(get_processor("finance"), FinanceProcessor)

    def test_career(self):
        assert isinstance(get_processor("career"), CareerBusinessProcessor)

    def test_business_alias(self):
        assert isinstance(get_processor("business"), CareerBusinessProcessor)

    def test_language(self):
        assert isinstance(get_processor("language"), LanguageLearningProcessor)

    def test_languages_alias(self):
        assert isinstance(get_processor("languages"), LanguageLearningProcessor)

    def test_creative(self):
        assert isinstance(get_processor("creative"), CreativeArtsProcessor)

    def test_hobbies_alias(self):
        assert isinstance(get_processor("hobbies"), CreativeArtsProcessor)

    def test_personal_development(self):
        assert isinstance(get_processor("personal_development"), PersonalDevelopmentProcessor)

    def test_relationships(self):
        assert isinstance(get_processor("relationships"), RelationshipsProcessor)

    def test_social_alias(self):
        assert isinstance(get_processor("social"), RelationshipsProcessor)

    def test_tech(self):
        assert isinstance(get_processor("tech"), TechSkillsProcessor)

    def test_technology_alias(self):
        assert isinstance(get_processor("technology"), TechSkillsProcessor)

    def test_travel(self):
        assert isinstance(get_processor("travel"), TravelAdventureProcessor)

    def test_adventure_alias(self):
        assert isinstance(get_processor("adventure"), TravelAdventureProcessor)

    def test_education(self):
        assert isinstance(get_processor("education"), EducationProcessor)

    def test_academic_alias(self):
        assert isinstance(get_processor("academic"), EducationProcessor)

    def test_other(self):
        p = get_processor("other")
        assert isinstance(p, BasePlanProcessor)

    def test_unknown(self):
        p = get_processor("zzzunknown")
        assert p is DEFAULT_PROCESSOR

    def test_none(self):
        p = get_processor(None)
        assert p is DEFAULT_PROCESSOR

    def test_empty(self):
        p = get_processor("")
        assert p is DEFAULT_PROCESSOR

    def test_case_insensitive(self):
        p = get_processor("HEALTH")
        assert isinstance(p, HealthFitnessProcessor)

    def test_with_whitespace(self):
        p = get_processor("  health  ")
        assert isinstance(p, HealthFitnessProcessor)


# ===================================================================
# BasePlanProcessor methods
# ===================================================================

class TestBasePlanProcessor:

    def test_default_has_no_rules(self):
        p = BasePlanProcessor()
        assert p.get_planning_rules() == ""
        assert p.get_calibration_hints() == ""
        assert p.get_validation_hints() == ""

    def test_health_has_rules(self):
        p = HealthFitnessProcessor()
        rules = p.get_planning_rules()
        assert "DOMAIN-SPECIFIC RULES" in rules
        assert "PROGRESSIVE OVERLOAD" in rules

    def test_health_has_calibration_hints(self):
        p = HealthFitnessProcessor()
        hints = p.get_calibration_hints()
        assert "DOMAIN-SPECIFIC CALIBRATION FOCUS" in hints
        assert "fitness level" in hints.lower()

    def test_finance_has_rules(self):
        p = FinanceProcessor()
        rules = p.get_planning_rules()
        assert "EMERGENCY FUND" in rules

    def test_career_has_rules(self):
        p = CareerBusinessProcessor()
        rules = p.get_planning_rules()
        assert "MARKET RESEARCH" in rules

    def test_language_has_rules(self):
        p = LanguageLearningProcessor()
        rules = p.get_planning_rules()
        assert "FOUR SKILLS" in rules

    def test_creative_has_rules(self):
        p = CreativeArtsProcessor()
        rules = p.get_planning_rules()
        assert "FUNDAMENTALS FIRST" in rules

    def test_personal_development_has_rules(self):
        p = PersonalDevelopmentProcessor()
        rules = p.get_planning_rules()
        assert "HABIT STACKING" in rules

    def test_relationships_has_rules(self):
        p = RelationshipsProcessor()
        rules = p.get_planning_rules()
        assert "SELF-WORK FIRST" in rules

    def test_tech_has_rules(self):
        p = TechSkillsProcessor()
        rules = p.get_planning_rules()
        assert "PROJECT-BASED" in rules

    def test_travel_has_rules(self):
        p = TravelAdventureProcessor()
        rules = p.get_planning_rules()
        assert "PREPARATION PHASES" in rules

    def test_education_has_rules(self):
        p = EducationProcessor()
        rules = p.get_planning_rules()
        assert "SYLLABUS FIRST" in rules

    def test_each_processor_has_display_name(self):
        for key, proc in PROCESSORS.items():
            assert proc.display_name, f"Processor for '{key}' has no display_name"
            assert proc.category, f"Processor for '{key}' has no category"


# ===================================================================
# detect_language()
# ===================================================================

class TestDetectLanguage:

    def test_french(self):
        assert detect_language("Je veux apprendre le piano") == "fr"

    def test_english(self):
        assert detect_language("I want to learn the piano") == "en"

    def test_spanish(self):
        assert detect_language("Yo quiero aprender para mi futuro") == "es"

    def test_empty_defaults_to_french(self):
        assert detect_language("") == "fr"

    def test_unknown_defaults_to_french(self):
        assert detect_language("asdfghjkl") == "fr"

    def test_mixed_language_dominant(self):
        # More French words should win
        text = "Je veux and I want but je suis dans une maison avec les gens"
        result = detect_language(text)
        assert result == "fr"


# ===================================================================
# detect_category_from_text()
# ===================================================================

class TestDetectCategoryFromText:

    def test_health(self):
        assert detect_category_from_text("Courir un marathon", "Je veux perdre du poids") == "health"

    def test_finance(self):
        assert detect_category_from_text("Investir en bourse", "devenir riche") == "finance"

    def test_career(self):
        assert detect_category_from_text("Lancer mon business", "devenir entrepreneur freelance") == "career"

    def test_language(self):
        assert detect_category_from_text("Apprendre le japonais", "passer le JLPT") == "language"

    def test_creative(self):
        assert detect_category_from_text("Apprendre la guitare", "jouer du piano et chant") == "creative"

    def test_tech(self):
        assert detect_category_from_text("Apprendre Python", "coding et développer une appli") == "tech"

    def test_travel(self):
        assert detect_category_from_text("Voyage au Japon", "randonnée en montagne") == "travel"

    def test_education(self):
        assert detect_category_from_text("Passer le bac", "réussir mon examen") == "education"

    def test_personal_development(self):
        assert detect_category_from_text("Lire plus de livres", "méditer et développement personnel") == "personal_development"

    def test_relationships(self):
        assert detect_category_from_text("Se faire des amis", "réseau social networking") == "relationships"

    def test_unknown_returns_other(self):
        assert detect_category_from_text("xyz", "abc") == "other"

    def test_empty_text(self):
        assert detect_category_from_text("", "") == "other"


# ===================================================================
# detect_category_with_ambiguity()
# ===================================================================

class TestDetectCategoryWithAmbiguity:

    def test_clear_category(self):
        result = detect_category_with_ambiguity("Courir un marathon", "running gym")
        assert result["is_ambiguous"] is False
        assert result["category"] == "health"

    def test_ambiguous_category(self):
        # Text with keywords from multiple categories
        result = detect_category_with_ambiguity(
            "Perdre du poids et méditer",
            "yoga sport mindfulness fitness meditation discipline"
        )
        # Could be health or personal_development
        assert "category" in result
        if result["is_ambiguous"]:
            assert len(result["candidates"]) == 2

    def test_no_match(self):
        result = detect_category_with_ambiguity("xyz", "abc")
        assert result["category"] == "other"
        assert result["is_ambiguous"] is False
        assert result["candidates"] == []


# ===================================================================
# _score_categories()
# ===================================================================

class TestScoreCategories:

    def test_scores_correctly(self):
        scores = _score_categories("je veux courir un marathon gym sport")
        assert "health" in scores
        assert scores["health"] >= 3

    def test_empty_text(self):
        scores = _score_categories("")
        assert scores == {}

    def test_no_matches(self):
        scores = _score_categories("xyzzy qqqqq")
        assert scores == {}


# ===================================================================
# CATEGORY_DISPLAY_NAMES
# ===================================================================

class TestCategoryDisplayNames:

    def test_all_processors_have_display_names(self):
        for cat in CATEGORY_DISPLAY_NAMES:
            assert cat in KEYWORD_MAP, f"Display name '{cat}' not in KEYWORD_MAP"

    def test_expected_categories_present(self):
        expected = ["health", "finance", "career", "language", "creative",
                    "personal_development", "relationships", "tech", "travel", "education"]
        for cat in expected:
            assert cat in CATEGORY_DISPLAY_NAMES, f"Missing display name for '{cat}'"


# ===================================================================
# KEYWORD_MAP
# ===================================================================

class TestKeywordMap:

    def test_all_categories_have_keywords(self):
        for cat in KEYWORD_MAP:
            assert len(KEYWORD_MAP[cat]) > 0, f"Category '{cat}' has no keywords"

    def test_health_keywords(self):
        assert "marathon" in KEYWORD_MAP["health"]
        assert "gym" in KEYWORD_MAP["health"]

    def test_finance_keywords(self):
        assert "invest" in KEYWORD_MAP["finance"]
        assert "budget" in KEYWORD_MAP["finance"]

    def test_tech_keywords(self):
        assert "python" in KEYWORD_MAP["tech"]
        assert "react" in KEYWORD_MAP["tech"]
