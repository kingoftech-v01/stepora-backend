"""
Category-specific plan processors for Stepora.

Each processor provides domain-specific rules, calibration questions,
and validation logic that get injected into the AI planning prompts.
This ensures plans are realistic and follow best practices for each domain.
"""


class BasePlanProcessor:
    """Base processor with default rules. Subclasses override for specialization."""

    category = "default"
    display_name = "Général"

    # Domain-specific rules injected into the planning prompt
    domain_rules = ""

    # Extra calibration questions specific to this domain
    extra_calibration_hints = ""

    # Validation rules for checking plan quality
    validation_hints = ""

    def get_planning_rules(self):
        """Return domain rules to inject into the planning system prompt."""
        if not self.domain_rules:
            return ""
        return f"""
DOMAIN-SPECIFIC RULES FOR {self.display_name.upper()} GOALS:
{self.domain_rules}
"""

    def get_calibration_hints(self):
        """Return extra hints for calibration question generation."""
        if not self.extra_calibration_hints:
            return ""
        return f"""
DOMAIN-SPECIFIC CALIBRATION FOCUS ({self.display_name}):
{self.extra_calibration_hints}
"""

    def get_validation_hints(self):
        """Return hints for validating plan quality."""
        if not self.validation_hints:
            return ""
        return self.validation_hints


class HealthFitnessProcessor(BasePlanProcessor):
    """Running, weight loss, bodybuilding, yoga, martial arts, sports."""

    category = "health"
    display_name = "Santé & Fitness"

    domain_rules = """
- PROGRESSIVE OVERLOAD: Increase intensity by max 10% per week (running distance, weight lifted, etc.)
- RECOVERY WEEKS: Every 3-4 weeks, reduce volume by 30-40% for recovery
- REST DAYS: Minimum 1-2 rest days per week. NEVER schedule intense exercise 7 days straight.
- WARM-UP/COOL-DOWN: Every exercise task must include warm-up (5-10 min) and cool-down/stretching (5-10 min)
- TAPER PERIOD: For race/competition goals, reduce volume 2-3 weeks before the event
- NUTRITION: Include nutrition-related tasks (meal planning, hydration tracking) at least once per week
- INJURY PREVENTION: Include mobility/flexibility work 2-3 times per week
- METRICS: Track specific numbers (distance, weight, reps, time) — never vague "improve"
- VARIETY: Alternate training types (cardio, strength, flexibility, rest) — never same workout 3 days in a row
- MEDICAL: If user mentions any injury, pain, or medical condition, FIRST task should be "Consult a doctor/physiotherapist"
- WEIGHT LOSS SPECIFIC: Maximum healthy weight loss is 0.5-1 kg per week. Set milestones accordingly (4-8 kg per month MAX).
- RUNNING SPECIFIC: Long run = 1x per week MAX. Easy runs at conversational pace. Speed work 1-2x per week after base is built.
- STRENGTH SPECIFIC: Focus on compound movements first. Rest 48h between working same muscle group.
"""

    extra_calibration_hints = """
- Ask about current fitness level with SPECIFIC metrics (how far can they run, how much can they lift)
- Ask about past injuries or physical limitations
- Ask if they've consulted a doctor recently
- Ask about their current diet and eating habits
- Ask about access to gym, equipment, or outdoor facilities
- Ask about sleep quality and stress levels
"""


class FinanceProcessor(BasePlanProcessor):
    """Investing, saving, budgeting, getting rich, financial freedom."""

    category = "finance"
    display_name = "Finance & Investissement"

    domain_rules = """
- EMERGENCY FUND FIRST: Before ANY investment, ensure user has 3-6 months emergency fund. Include this as milestone 1 if not mentioned.
- DEBT MANAGEMENT: If user has high-interest debt, prioritize paying it off before investing.
- DIVERSIFICATION: Never recommend putting all money in one asset class. Teach diversification principles.
- REALISTIC RETURNS: Stock market averages 7-10% annually. Do NOT promise higher returns. "Getting rich quick" is unrealistic.
- BUDGET RULE: Teach the 50/30/20 rule (needs/wants/savings) or similar framework.
- COMPOUND INTEREST: Explain and leverage compound interest in long-term plans.
- RISK ASSESSMENT: Include a task to assess risk tolerance before any investment.
- LEGAL/TAX: Include tasks about understanding tax implications of investments.
- PROFESSIONAL REFERRAL: ALWAYS recommend consulting a certified financial advisor for amounts > 10,000€.
- SCAM AWARENESS: Include a task about recognizing financial scams and too-good-to-be-true offers.
- EDUCATION BEFORE ACTION: First 30% of the plan should be pure financial education, not action.
- PROGRESSIVE AMOUNTS: Start with small investments (10-50€) and increase gradually as knowledge grows.
- TRACKING: Include weekly/monthly budget review and net worth tracking tasks.
"""

    extra_calibration_hints = """
- Ask about current income and expenses (monthly)
- Ask about existing savings and debts
- Ask about financial knowledge level (beginner/intermediate/advanced)
- Ask about risk tolerance (conservative/moderate/aggressive)
- Ask about financial goals specifics (amount, timeline, purpose)
- Ask if they have dependents (family financial obligations)
"""


class CareerBusinessProcessor(BasePlanProcessor):
    """Starting a business, career change, promotion, freelancing, side hustle."""

    category = "career"
    display_name = "Carrière & Business"

    domain_rules = """
- MARKET RESEARCH FIRST: First milestone should ALWAYS include market research, competitor analysis, and target audience definition.
- LEGAL SETUP: Include tasks for legal registration (auto-entrepreneur, SARL, etc.), business bank account, insurance.
- MVP APPROACH: Start with minimum viable product/service. Do NOT plan a perfect launch — plan an iterative one.
- FINANCIAL PLANNING: Include business budget, pricing strategy, and break-even analysis tasks.
- MARKETING STRATEGY: Include at least 3 different marketing channels (social media, SEO, networking, etc.)
- NETWORKING: Include tasks to connect with mentors, join professional groups, attend events.
- CUSTOMER FEEDBACK: Include regular tasks to gather and incorporate customer/market feedback.
- TIME MANAGEMENT: If this is a side project alongside a job, respect the constraint — plan realistically for evenings/weekends.
- MILESTONES: Use business milestones (first customer, first sale, first 100€ revenue, break-even, etc.)
- TOOLS: Recommend specific free/low-cost tools (Canva, Shopify, WordPress, Notion, Google Workspace, etc.)
- RISKS: Include a task to identify and plan for business risks and failure scenarios.
- LEGAL COMPLIANCE: Include tasks for CGV, RGPD, privacy policy if selling online.
"""

    extra_calibration_hints = """
- Ask about their current job/income situation
- Ask about specific business idea details (product, service, target market)
- Ask about budget available for the business
- Ask about time available (full-time or side project)
- Ask about existing skills relevant to the business
- Ask about competition they've already identified
"""


class LanguageLearningProcessor(BasePlanProcessor):
    """Learning any foreign language, passing language exams."""

    category = "language"
    display_name = "Apprentissage de Langues"

    domain_rules = """
- FOUR SKILLS: Every week must include practice of ALL 4 skills: reading, writing, listening, speaking. Never focus on just one.
- SPACED REPETITION: Use spaced repetition for vocabulary (Anki, Memrise, etc.). Include daily 10-15 min vocab review.
- IMMERSION: Gradually increase immersion (songs, podcasts, movies, news) from month 2 onwards.
- GRAMMAR: Introduce grammar progressively — never dump all grammar at once. 1-2 new grammar points per week maximum.
- CONVERSATION PRACTICE: Include speaking practice with real humans (tandem partners, tutors) from month 2 at latest.
- EXAM-SPECIFIC: If preparing for an exam (JLPT, DELF, TOEFL, etc.), include mock tests monthly from midpoint onwards.
- REALISTIC EXPECTATIONS:
  * A1→A2: ~150-200 hours. A2→B1: ~200-300 hours. B1→B2: ~300-400 hours.
  * Japanese/Chinese/Arabic: multiply by 2-3x due to writing systems.
  * Set milestones around CEFR or exam levels, not vague "be fluent".
- WRITING SYSTEM: For languages with different scripts (Japanese, Arabic, Korean, Chinese), master the writing system FIRST.
- CULTURAL CONTEXT: Include cultural learning tasks (customs, media, food, history) alongside language.
- RESOURCES: Recommend specific tools per language (Genki for Japanese, Assimil for French, Duolingo for basics, etc.)
- DAILY PRACTICE: Short daily sessions (20-30 min) are more effective than long weekly sessions. Plan accordingly.
- PLATEAU MANAGEMENT: Include variety tasks to avoid plateau (switch textbooks, try new media, change routine) every 4-6 weeks.
"""

    extra_calibration_hints = """
- Ask about current level in the target language (complete beginner, knows basics, etc.)
- Ask about any other languages they speak (language learning experience)
- Ask about specific goal (exam, travel, work, fun)
- Ask about preferred learning style (visual, auditory, reading)
- Ask about access to native speakers or language communities
- Ask about exposure to the language (media, travel history)
"""


class CreativeArtsProcessor(BasePlanProcessor):
    """Music, art, writing, photography, cooking, crafts."""

    category = "creative"
    display_name = "Arts & Créativité"

    domain_rules = """
- FUNDAMENTALS FIRST: Start with foundations (music theory, color theory, cooking basics, etc.) before creative exploration.
- DAILY PRACTICE: Include short daily practice (15-30 min minimum). Consistency > intensity for creative skills.
- TECHNIQUE + CREATIVITY: Alternate between technical exercises and creative projects. Never only one.
- MENTOR/TEACHER: Recommend finding a teacher or mentor for technique correction (especially music instruments, painting).
- PROJECTS: Include concrete creative projects (play a song, cook a meal for friends, write a short story) as milestones.
- INSPIRATION: Include tasks to study masters/references in the field (listen to great musicians, visit galleries, read published authors).
- FEEDBACK: Include regular peer review or sharing tasks (play for friends, share writing, etc.)
- TOOLS & MATERIALS: Specify exactly what tools/materials are needed and when to acquire them.
- MUSIC SPECIFIC: Practice scales/technique daily + learn pieces. Don't rush — master fundamentals.
- COOKING SPECIFIC: Start with simple recipes, build to complex. Include knife skills, timing, and meal planning.
- WRITING SPECIFIC: Include regular writing exercises (prompts, journaling) + reading in the genre.
- ART SPECIFIC: Include sketching daily + study of fundamentals (perspective, anatomy, light/shadow).
- PROGRESSION: Increase difficulty of pieces/recipes/projects gradually. Track specific skills mastered.
"""

    extra_calibration_hints = """
- Ask about current skill level in this creative area
- Ask about equipment/tools they already have
- Ask about specific creative goals (perform, exhibit, publish, personal enjoyment)
- Ask about time available for daily practice
- Ask about creative influences and inspirations
- Ask about willingness to take formal lessons
"""


class PersonalDevelopmentProcessor(BasePlanProcessor):
    """Habits, meditation, confidence, public speaking, self-improvement, reading."""

    category = "personal_development"
    display_name = "Développement Personnel"

    domain_rules = """
- HABIT STACKING: Build new habits by attaching them to existing routines. Include specific "when/where/how" for each habit.
- START TINY: Begin with micro-habits (2 min meditation, 1 page reading, 1 push-up) and grow gradually.
- TRACKING: Include daily habit tracking tasks. Use a simple yes/no tracker.
- 21/66 DAY RULE: Habits take 21-66 days to form. Plan accordingly — don't change routines too fast.
- ACCOUNTABILITY: Include tasks to share goals with someone or find an accountability partner.
- REFLECTION: Include weekly reflection tasks (journal, self-assessment) to track inner progress.
- SETBACK PLANNING: Include "if I miss a day" plans — never plan as if the user will be perfect.
- MEDITATION: Start with 2-5 minutes and add 1-2 minutes per week. Recommend guided meditation apps (Headspace, Calm, Insight Timer).
- PUBLIC SPEAKING: Progress from mirror practice → recording → small group → larger audience. Include specific speech preparation tasks.
- READING: Set realistic goals (20-30 pages/day or 1 book/month). Include active reading tasks (notes, summaries, discussions).
- CONFIDENCE: Include concrete exposure tasks (small challenges that build to bigger ones). Never just "be more confident".
- JOURNALING: Include specific prompts, not just "write in journal". Gratitude, reflection, planning, emotion processing.
- SOCIAL SKILLS: Include specific social challenges (start 1 conversation, attend 1 event, etc.) with gradual increase.
"""

    extra_calibration_hints = """
- Ask about current habits and daily routine
- Ask about previous attempts at self-improvement (what worked, what failed)
- Ask about their biggest personal challenge right now
- Ask about support system (friends, family, community)
- Ask about what triggers their desire for change
- Ask about how they handle setbacks
"""


class RelationshipsProcessor(BasePlanProcessor):
    """Networking, dating, family, friendships, social skills."""

    category = "relationships"
    display_name = "Relations & Social"

    domain_rules = """
- SELF-WORK FIRST: Before focusing on others, include self-reflection tasks (values, boundaries, communication style).
- GRADUAL EXPOSURE: Progress from low-risk social situations to higher-risk ones gradually.
- SPECIFIC ACTIONS: Include concrete actionable social tasks (message 1 person, attend 1 event, invite someone for coffee).
- COMMUNICATION SKILLS: Include tasks on active listening, non-violent communication, and emotional intelligence.
- NETWORKING: Include specific platforms and strategies (LinkedIn, Meetup, professional events, hobby groups).
- QUALITY OVER QUANTITY: Focus on deepening existing relationships alongside building new ones.
- BOUNDARIES: Include tasks on setting and maintaining healthy boundaries.
- VULNERABILITY: Include gradual exercises in sharing and opening up to build deeper connections.
- DIGITAL & IN-PERSON: Balance online and face-to-face interaction tasks.
- FOLLOW-UP: Include follow-up tasks after social interactions (send message, plan next meeting).
- PROFESSIONAL REFERRAL: For deep relationship issues, family trauma, or social anxiety, recommend a therapist/counselor.
- CULTURAL SENSITIVITY: Respect cultural differences in social expectations and communication styles.
"""

    extra_calibration_hints = """
- Ask about current social circle (size, satisfaction)
- Ask about specific relationship goal (romantic, professional, friendship)
- Ask about social comfort level (introvert/extrovert)
- Ask about past social challenges
- Ask about available social venues/communities
- Ask about any social anxiety or specific fears
"""


class TechSkillsProcessor(BasePlanProcessor):
    """Programming, IT, digital skills, certifications, data science."""

    category = "tech"
    display_name = "Compétences Techniques"

    domain_rules = """
- PROJECT-BASED LEARNING: After basics, learn by building real projects. Every 2-3 weeks, complete a project.
- FUNDAMENTALS FIRST: Don't skip basics — learn core concepts before frameworks/tools.
- HANDS-ON: Every theoretical task must be paired with a practical exercise. Read, then code.
- VERSION CONTROL: Include Git basics early. All projects should be version-controlled from the start.
- PORTFOLIO: Build a portfolio throughout the plan. Each project becomes a portfolio piece.
- DOCUMENTATION: Include tasks to document what you learn (blog, notes, README files).
- COMMUNITY: Include tasks to join relevant communities (GitHub, Stack Overflow, Discord, Reddit).
- CERTIFICATION PREP: If targeting a cert, include practice exams from midpoint onwards.
- DEBUGGING: Include specific debugging and problem-solving exercises.
- CODE REVIEW: Include tasks to read other people's code and get feedback on yours.
- RESOURCES: Recommend specific platforms (freeCodeCamp, Coursera, Udemy, YouTube channels, official docs).
- ENVIRONMENT SETUP: First task should ALWAYS be setting up the development environment properly.
- PROGRESSIVE COMPLEXITY: Start with simple programs/scripts, build to full applications.
"""

    extra_calibration_hints = """
- Ask about current technical skill level
- Ask about specific technology/language they want to learn
- Ask about their computer setup and OS
- Ask about goal (career change, certification, personal project, job requirement)
- Ask about preferred learning format (video, text, interactive)
- Ask about any programming experience in other languages
"""


class TravelAdventureProcessor(BasePlanProcessor):
    """Travel planning, outdoor activities, extreme sports, exploration."""

    category = "travel"
    display_name = "Voyage & Aventure"

    domain_rules = """
- PREPARATION PHASES: Divide into Research → Planning → Preparation → Execution → Debrief.
- BUDGET PLANNING: Include detailed budget tasks (transport, accommodation, food, activities, emergency fund).
- DOCUMENTS: Include tasks for visas, passports, insurance, vaccinations if applicable.
- PHYSICAL PREP: For adventure/outdoor goals, include physical training ramp-up.
- GEAR: Include specific gear research, purchase, and testing tasks well before the trip.
- SAFETY: Include safety planning (emergency contacts, route sharing, first aid knowledge).
- CULTURAL PREP: Include cultural research (customs, language basics, etiquette) for international travel.
- BOOKING TIMELINE: Plan bookings at optimal times (flights 2-3 months ahead, accommodations 1-2 months).
- PACKING: Include a packing task with specific checklists appropriate to the destination.
- EXTREME SPORTS: ALWAYS recommend professional instruction and proper certification.
- HIKING/TREKKING: Include progressive distance training, altitude acclimatization if relevant.
- PHOTOGRAPHY: Include tasks for preparing camera gear and learning destination-specific techniques.
"""

    extra_calibration_hints = """
- Ask about destination and travel dates
- Ask about budget available
- Ask about travel experience level
- Ask about physical fitness level (for adventure activities)
- Ask about traveling solo, with partner, or group
- Ask about any medical conditions or dietary restrictions
"""


class EducationProcessor(BasePlanProcessor):
    """Academic goals, exams, certifications, continuing education."""

    category = "education"
    display_name = "Éducation & Examens"

    domain_rules = """
- SYLLABUS FIRST: Start by getting the exact syllabus/curriculum/exam content breakdown.
- STUDY SCHEDULE: Create a structured study schedule that covers ALL topics before the exam date.
- ACTIVE RECALL: Use active recall (self-testing, flashcards) over passive reading. Include daily review sessions.
- SPACED REPETITION: Schedule review of previously learned material at increasing intervals.
- PRACTICE EXAMS: Include mock exams/practice tests starting from 50% of the timeline, weekly from 75% onwards.
- WEAK AREAS: Include regular self-assessment to identify and focus on weak areas.
- STUDY GROUPS: Recommend finding study partners or groups for accountability and discussion.
- BREAKS: Follow the Pomodoro technique or similar — include specific break schedules.
- MATERIALS: Specify exact textbooks, courses, or resources needed with acquisition tasks.
- NOTE-TAKING: Include structured note-taking tasks (Cornell method, mind maps, summaries).
- EXAM STRATEGY: Include exam-taking strategies (time management, question prioritization).
- TAPER: Last 1-2 weeks should be light review only — no new material. Include rest before exam day.
"""

    extra_calibration_hints = """
- Ask about the specific exam/certification/degree
- Ask about current knowledge of the subject
- Ask about study habits and preferences
- Ask about available study time per week
- Ask about access to study materials and resources
- Ask about exam date and registration status
"""


# Registry of all processors
PROCESSORS = {
    "health": HealthFitnessProcessor(),
    "fitness": HealthFitnessProcessor(),
    "finance": FinanceProcessor(),
    "career": CareerBusinessProcessor(),
    "business": CareerBusinessProcessor(),
    "language": LanguageLearningProcessor(),
    "languages": LanguageLearningProcessor(),
    "creative": CreativeArtsProcessor(),
    "hobbies": CreativeArtsProcessor(),
    "personal_development": PersonalDevelopmentProcessor(),
    "relationships": RelationshipsProcessor(),
    "social": RelationshipsProcessor(),
    "tech": TechSkillsProcessor(),
    "technology": TechSkillsProcessor(),
    "travel": TravelAdventureProcessor(),
    "adventure": TravelAdventureProcessor(),
    "education": EducationProcessor(),
    "academic": EducationProcessor(),
    "other": BasePlanProcessor(),
}

# Default processor
DEFAULT_PROCESSOR = BasePlanProcessor()


def get_processor(category: str) -> BasePlanProcessor:
    """Get the appropriate processor for a dream category."""
    if not category:
        return DEFAULT_PROCESSOR
    return PROCESSORS.get(category.lower().strip(), DEFAULT_PROCESSOR)


def detect_language(text: str) -> str:
    """
    Simple heuristic language detection from text.
    Returns ISO code: 'fr', 'en', 'es', etc. Defaults to 'fr'.
    """
    text_lower = text.lower()
    # French indicators
    fr_words = [
        "je",
        "veux",
        "mon",
        "ma",
        "mes",
        "une",
        "des",
        "les",
        "dans",
        "pour",
        "avec",
        "sur",
        "est",
        "sont",
        "faire",
        "cette",
        "mais",
        "pas",
        "que",
        "qui",
        "aussi",
        "plus",
        "tout",
        "être",
        "avoir",
        "aller",
    ]
    # English indicators
    en_words = [
        "i ",
        "my",
        "the",
        "and",
        "to ",
        "a ",
        "in ",
        "for",
        "with",
        "want",
        "get",
        "have",
        "this",
        "that",
        "from",
        "will",
        "can",
        "more",
        "just",
        "be ",
        "not",
        "all",
        "would",
        "make",
        "like",
        "so ",
    ]
    # Spanish indicators
    es_words = [
        "yo ",
        "mi ",
        "quiero",
        "para",
        "con",
        "una",
        "los",
        "las",
        "por",
        "como",
        "más",
        "pero",
        "este",
        "esta",
        "todo",
        "hacer",
        "ser",
    ]

    fr_score = sum(1 for w in fr_words if w in text_lower)
    en_score = sum(1 for w in en_words if w in text_lower)
    es_score = sum(1 for w in es_words if w in text_lower)

    scores = {"fr": fr_score, "en": en_score, "es": es_score}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "fr"  # default
    return best


KEYWORD_MAP = {
    "health": [
        "courir",
        "running",
        "marathon",
        "gym",
        "muscul",
        "yoga",
        "sport",
        "perdre du poids",
        "lose weight",
        "maigrir",
        "fitness",
        "exercise",
        "santé",
        "health",
        "méditation",
        "natation",
        "swim",
        "vélo",
        "cycling",
        "boxe",
        "boxing",
        "martial",
        "karate",
        "judo",
        "abdos",
        "pompes",
        "poids",
        "kg",
        "kilos",
        "diet",
        "régime",
        "nutrition",
    ],
    "finance": [
        "riche",
        "rich",
        "argent",
        "money",
        "invest",
        "bourse",
        "stock",
        "épargne",
        "saving",
        "budget",
        "financ",
        "crypto",
        "bitcoin",
        "patrimoine",
        "wealth",
        "revenus passifs",
        "passive income",
        "immobilier",
        "real estate",
        "retraite",
        "retirement",
    ],
    "career": [
        "business",
        "entreprise",
        "startup",
        "boutique",
        "commerce",
        "carrière",
        "career",
        "promotion",
        "freelance",
        "emploi",
        "job",
        "salaire",
        "salary",
        "entrepreneur",
        "vendre",
        "sell",
        "client",
        "manager",
        "leadership",
        "side hustle",
        "e-commerce",
    ],
    "language": [
        "langue",
        "language",
        "japonais",
        "japanese",
        "anglais",
        "english",
        "espagnol",
        "spanish",
        "allemand",
        "german",
        "chinois",
        "chinese",
        "coréen",
        "korean",
        "arabe",
        "arabic",
        "italien",
        "italian",
        "portugais",
        "portuguese",
        "russe",
        "russian",
        "jlpt",
        "delf",
        "toefl",
        "ielts",
        "toeic",
        "hsk",
    ],
    "creative": [
        "guitare",
        "guitar",
        "piano",
        "musique",
        "music",
        "chant",
        "sing",
        "peindre",
        "paint",
        "dessin",
        "draw",
        "photo",
        "écrire",
        "write",
        "roman",
        "novel",
        "cuisine",
        "cook",
        "recette",
        "recipe",
        "danse",
        "dance",
        "sculpture",
        "poterie",
        "pottery",
        "tricot",
        "instrument",
        "violon",
        "violin",
        "batterie",
        "drums",
    ],
    "personal_development": [
        "habitude",
        "habit",
        "confiance",
        "confidence",
        "méditer",
        "meditat",
        "lire",
        "read",
        "livre",
        "book",
        "journal",
        "productiv",
        "discipline",
        "organisation",
        "organiz",
        "anxiété",
        "anxiety",
        "stress",
        "mindfulness",
        "bien-être",
        "public speaking",
        "parler en public",
        "motivation",
        "changer ma vie",
        "meilleure version",
        "transformer",
        "développement personnel",
        "self improvement",
        "routine",
        "se lever tôt",
        "procrastin",
        "objectifs",
        "goals",
    ],
    "relationships": [
        "ami",
        "friend",
        "relation",
        "dating",
        "rencontre",
        "meet",
        "réseau",
        "network",
        "social",
        "famille",
        "family",
        "couple",
        "mariage",
        "marriage",
        "communication",
        "timide",
        "shy",
        "timidité",
        "solitude",
        "introverti",
        "sortir plus",
        "parler aux gens",
        "confiance en soi",
    ],
    "tech": [
        "programm",
        "coder",
        "coding",
        "python",
        "javascript",
        "web dev",
        "développ",
        "develop",
        "appli",
        "logiciel",
        "software",
        "data science",
        "machine learning",
        "intelligence artificielle",
        "cybersécurité",
        "cybersecurity",
        "cloud computing",
        "devops",
        "api",
        "base de données",
        "database",
        "frontend",
        "backend",
        "react",
        "django",
        "flutter",
        "html",
        "css",
    ],
    "travel": [
        "voyage",
        "travel",
        "trek",
        "randonn",
        "hike",
        "hiking",
        "escalade",
        "climb",
        "plongée",
        "diving",
        "surf",
        "ski",
        "parachute",
        "aventure",
        "adventure",
        "backpack",
        "tour du monde",
        "mont blanc",
        "camping",
        "tente",
        "bivouac",
        "sentier",
        "montagne",
        "mountain",
        "altitude",
        "expédition",
        "expedition",
        "road trip",
        "sac à dos",
        "autonomie",
    ],
    "education": [
        "examen",
        "exam",
        "diplôme",
        "degree",
        "université",
        "university",
        "bac",
        "concours",
        "certifi",
        "formation",
        "training",
        "étude",
        "study",
        "master",
        "licence",
        "doctorat",
        "phd",
        "permis",
        "driving license",
        "driver's license",
        "réussir",
        "passer le",
        "préparer le",
        "réviser",
    ],
}

# Display names for disambiguation questions
CATEGORY_DISPLAY_NAMES = {
    "health": "Santé & Fitness",
    "finance": "Finance & Investissement",
    "career": "Carrière & Business",
    "language": "Apprentissage de Langues",
    "creative": "Arts & Créativité",
    "personal_development": "Développement Personnel",
    "relationships": "Relations & Social",
    "tech": "Compétences Techniques",
    "travel": "Voyage & Aventure",
    "education": "Éducation & Examens",
}


def _score_categories(text: str) -> dict:
    """Score all categories against text. Returns {category: score}."""
    scores = {}
    for cat, keywords in KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    return scores


def detect_category_from_text(title: str, description: str) -> str:
    """
    Heuristic category detection from dream text.
    Used as fallback when AI analysis category is missing or 'other'.
    """
    text = f"{title} {description}".lower()
    scores = _score_categories(text)

    if scores:
        return max(scores, key=scores.get)
    return "other"


def detect_category_with_ambiguity(title: str, description: str) -> dict:
    """
    Detect category with ambiguity info. Returns:
    {
        'category': str,           # best guess
        'is_ambiguous': bool,      # True if top-2 scores are close
        'candidates': list[str],   # top-2 categories if ambiguous
    }
    """
    text = f"{title} {description}".lower()
    scores = _score_categories(text)

    if not scores:
        return {"category": "other", "is_ambiguous": False, "candidates": []}

    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = sorted_cats[0]

    if len(sorted_cats) >= 2:
        second_cat, second_score = sorted_cats[1]
        # Ambiguous if second category has >= 60% of the best score
        # and both have at least 2 keyword hits
        if second_score >= best_score * 0.6 and second_score >= 2:
            return {
                "category": best_cat,
                "is_ambiguous": True,
                "candidates": [best_cat, second_cat],
            }

    return {"category": best_cat, "is_ambiguous": False, "candidates": [best_cat]}
