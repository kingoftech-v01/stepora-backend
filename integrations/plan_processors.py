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


class HomeRenovationProcessor(BasePlanProcessor):
    """Home renovation, remodeling, interior design, landscaping."""

    category = "home_renovation"
    display_name = "Rénovation & Maison"

    domain_rules = """
- CONTRACTOR VETTING: Include tasks for getting multiple quotes (minimum 3), checking references, verifying insurance/licenses.
- PERMITS & REGULATIONS: ALWAYS include a task to check local building permits and regulations BEFORE any work begins.
- BUDGET WITH CONTINGENCY: Plan budget with a mandatory 20% contingency for unexpected issues. Track expenses per room/phase.
- ROOM-BY-ROOM APPROACH: Tackle one room or zone at a time. Never renovate the entire house simultaneously unless professionally managed.
- DIY VS PROFESSIONAL: Clearly distinguish tasks the user can DIY vs those requiring licensed professionals (electrical, plumbing, structural).
- MATERIAL SOURCING: Include tasks for material research, price comparison, ordering lead times (some materials take 4-8 weeks).
- TIMELINE WITH DRYING/CURING: Account for drying times (paint: 24-48h, concrete: 28 days, grout: 24h, varnish: 48-72h).
- SAFETY FIRST: Include safety tasks — asbestos testing for pre-1997 buildings, lead paint testing, electrical safety checks.
- SEASONAL CONSIDERATIONS: Plan exterior work for dry/warm seasons. Interior work can be year-round but consider heating/ventilation.
- INSPECTION MILESTONES: Include inspection checkpoints before covering work (plumbing pressure test, electrical inspection before closing walls).
- ORDER OF OPERATIONS: Follow correct sequence — demolition → structural → plumbing/electrical → insulation → walls → flooring → finishing.
- LIVING ARRANGEMENTS: If renovating primary residence, plan temporary living arrangements or phased approach to maintain livability.
"""

    extra_calibration_hints = """
- Ask about the scope of renovation (single room, full house, specific system)
- Ask about the current state of the property (age, known issues)
- Ask about total budget available
- Ask about DIY experience and comfort level
- Ask about timeline constraints (moving date, seasonal deadlines)
- Ask about whether they will live in the home during renovation
"""


class DIYCraftProcessor(BasePlanProcessor):
    """DIY projects, woodworking, sewing, knitting, jewelry making, crafts."""

    category = "diy"
    display_name = "Bricolage & DIY"

    domain_rules = """
- TOOL ACQUISITION PROGRESSION: Start with essential tools only. Add specialized tools as skills grow — don't buy everything upfront.
- SAFETY EQUIPMENT FIRST: ALWAYS include safety gear acquisition as the very first task (goggles, gloves, dust mask, ear protection as appropriate).
- PRACTICE ON SCRAP: Before starting the actual project, include practice tasks on scrap/cheap materials to build confidence.
- PROJECT COMPLEXITY LADDER: Start with simple beginner projects and progress to intermediate/advanced. Never jump to complex projects.
- MEASUREMENT PRECISION: Include tasks to learn and practice precise measurement — "measure twice, cut once" principle.
- MATERIAL COST TRACKING: Include a budget tracker for materials. Suggest where to source materials (hardware stores, online, reclaimed).
- WORKSHOP ORGANIZATION: Include tasks for workspace setup, storage solutions, and keeping a clean/safe work area.
- FINISHING TECHNIQUES: Dedicate specific tasks to finishing (sanding, staining, painting, sealing, pressing, blocking) — don't rush the finish.
- TIME ESTIMATES PER SKILL LEVEL: Provide realistic time estimates. Beginners take 2-3x longer than experienced crafters.
- PATTERN/PLAN READING: Include tasks to learn how to read patterns, blueprints, or project plans before starting.
- MISTAKES AS LEARNING: Plan for mistakes — include extra material in the budget and frame errors as learning opportunities.
"""

    extra_calibration_hints = """
- Ask about current skill level in the specific craft
- Ask about tools and workspace already available
- Ask about budget for materials and tools
- Ask about the specific project they want to create
- Ask about time available for crafting (daily/weekly)
- Ask about any previous craft experience in other domains
"""


class ParentingProcessor(BasePlanProcessor):
    """Parenting skills, child development, family planning, pregnancy."""

    category = "parenting"
    display_name = "Parentalité & Famille"

    domain_rules = """
- AGE-APPROPRIATE MILESTONES: All tasks and goals must be calibrated to the child's age and developmental stage.
- CONSISTENCY OVER PERFECTION: Emphasize consistent routines and approaches rather than perfect execution. Include self-compassion tasks.
- PARTNER ALIGNMENT: Include tasks for discussing and aligning parenting approaches with partner/co-parent. Teamwork is essential.
- SELF-CARE ALONGSIDE PARENTING: ALWAYS include parent self-care tasks (rest, hobbies, social time). Burnout prevention is critical.
- PROFESSIONAL REFERRAL: For behavioral concerns, developmental delays, or emotional difficulties, include tasks to consult pediatricians, child psychologists, or specialists.
- DOCUMENTATION & MEMORY KEEPING: Include tasks for documenting milestones, keeping a journal, or creating memory books.
- ROUTINE ESTABLISHMENT: Include concrete routine-building tasks with specific times and activities (morning routine, bedtime routine, meal schedule).
- GRADUAL INDEPENDENCE: Build tasks that progressively give children age-appropriate autonomy and responsibility.
- SIBLING DYNAMICS: If multiple children, include tasks addressing sibling relationships, fairness, and individual attention time.
- SCHOOL/DAYCARE TRANSITION: Include preparation tasks for major transitions (starting daycare, school entry, grade changes).
- COMMUNITY CONNECTION: Include tasks to connect with other parents (playgroups, parent associations, online communities).
- PATIENCE & FLEXIBILITY: Build buffer time into every milestone — children develop at their own pace.
"""

    extra_calibration_hints = """
- Ask about the child's age (or pregnancy stage)
- Ask about specific parenting challenge or goal
- Ask about family structure (single parent, co-parenting, extended family support)
- Ask about current routines and what's working/not working
- Ask about any special needs or concerns about the child
- Ask about partner alignment on parenting approach
"""


class PetCareProcessor(BasePlanProcessor):
    """Pet care, training, adoption, animal husbandry."""

    category = "pets"
    display_name = "Animaux & Soins"

    domain_rules = """
- VETERINARY CHECKUPS FIRST: First milestone must include a veterinary visit for health assessment, vaccinations, and baseline checks.
- TRAINING CONSISTENCY: Training tasks must be short (5-15 min sessions), daily, and use positive reinforcement consistently.
- SOCIALIZATION WINDOWS: For puppies/kittens, include critical socialization tasks within the appropriate window (3-14 weeks for puppies, 2-7 weeks for kittens).
- NUTRITION RESEARCH: Include tasks to research and select appropriate food for breed, age, and health conditions. Consult vet for diet plans.
- EXERCISE APPROPRIATE TO BREED/SPECIES: Tailor exercise plans to the specific animal — never over-exercise puppies or brachycephalic breeds.
- GROOMING SCHEDULE: Include regular grooming tasks appropriate to the animal (brushing, nail trimming, dental care, bathing).
- PET-PROOFING HOME: Include tasks to make the home safe (toxic plants, secure cabinets, electrical cords, escape-proofing).
- EMERGENCY PREPAREDNESS: Include tasks for assembling a pet first-aid kit, identifying emergency vet clinics, and learning basic pet first aid.
- BEHAVIORAL PATIENCE: Set realistic behavior change timelines — training takes weeks to months. Include regression planning.
- BONDING ACTIVITIES: Include specific bonding tasks (play sessions, quiet time together, enrichment activities, walks/outings).
- IDENTIFICATION: Include tasks for microchipping, ID tags, and registration.
- COST PLANNING: Include budget planning for ongoing costs (food, vet, insurance, grooming, boarding).
"""

    extra_calibration_hints = """
- Ask about the type of animal (species, breed, age)
- Ask about whether this is a new pet or existing pet
- Ask about specific goals (training, health improvement, adoption preparation)
- Ask about current living situation (house, apartment, yard access)
- Ask about other pets in the household
- Ask about previous pet ownership experience
"""


class GardeningProcessor(BasePlanProcessor):
    """Gardening, vegetable growing, permaculture, landscaping, plant care."""

    category = "gardening"
    display_name = "Jardinage & Agriculture"

    domain_rules = """
- SEASONAL CALENDAR ESSENTIAL: ALL planting and gardening tasks must follow the local seasonal calendar. Include a planting schedule as milestone 1.
- SOIL TESTING FIRST: Include a soil test task BEFORE any planting. Soil pH, nutrients, and composition determine what will grow successfully.
- START SMALL THEN EXPAND: Begin with a small manageable area or a few plants. Expand only after the first season's success.
- COMPANION PLANTING: Include tasks to learn and apply companion planting principles — some plants help each other, others compete.
- PEST MANAGEMENT: Include integrated pest management tasks with organic methods preferred (neem oil, companion planting, beneficial insects).
- WATERING SCHEDULES: Include specific watering schedules adapted to plant type, season, and climate. Overwatering kills more plants than underwatering.
- SUNLIGHT REQUIREMENTS: Include tasks to assess and map sunlight in the garden (full sun, partial shade, shade areas).
- HARVEST TIMING: Include tasks for learning harvest indicators for each crop — harvesting too early or late reduces quality.
- SEED STARTING VS TRANSPLANTS: Advise on which plants to start from seed vs buying transplants based on difficulty and season timing.
- COMPOSTING: Include composting setup and maintenance tasks as a sustainable soil improvement strategy.
- TOOL MAINTENANCE: Include regular tool cleaning, sharpening, and storage tasks to extend tool life.
- RECORD KEEPING: Include a garden journal for tracking what was planted, when, where, and results for future season planning.
- WEATHER MONITORING: Include tasks for monitoring weather forecasts and protecting plants from frost, heat, or storms.
"""

    extra_calibration_hints = """
- Ask about available garden space (size, type — balcony, yard, allotment)
- Ask about climate zone and local growing conditions
- Ask about what they want to grow (vegetables, flowers, herbs, fruit trees)
- Ask about current gardening experience level
- Ask about time available for garden maintenance (daily/weekly)
- Ask about water access and irrigation options
"""


class RealEstateProcessor(BasePlanProcessor):
    """Buying property, mortgages, rental investment, homeownership."""

    category = "real_estate"
    display_name = "Immobilier & Investissement"

    domain_rules = """
- CREDIT SCORE OPTIMIZATION FIRST: Start by reviewing and improving credit score. Include tasks for credit report review, dispute errors, and debt-to-income ratio optimization.
- DOWN PAYMENT SAVINGS PLAN: Create a structured savings plan for the down payment with monthly targets and timeline.
- MARKET RESEARCH: Include tasks for researching location, price trends, neighborhood analysis, school districts, and comparable sales.
- PRE-APPROVAL BEFORE HUNTING: Get mortgage pre-approval BEFORE house hunting. Include tasks for document preparation and lender comparison.
- INSPECTION CHECKLIST: Include a thorough property inspection checklist (structural, electrical, plumbing, roof, foundation, pests, mold, HVAC).
- NEGOTIATION STRATEGIES: Include tasks for learning negotiation tactics, understanding seller motivations, preparing counter-offers, and knowing when to walk away.
- MORTGAGE COMPARISON: Compare at least 3 mortgage offers. Include tasks for understanding fixed vs variable rates, amortization, total cost of borrowing.
- CLOSING COSTS BUDGET: Budget 2-5% of purchase price for closing costs. Include all fees (notary, registration, insurance, taxes, inspection fees).
- FIRST-TIME BUYER PROGRAMS: Research government programs, tax credits, PTZ (Prêt à Taux Zéro), and first-time buyer incentives.
- RENTAL INVESTMENT CASH FLOW: For rental goals, include cash flow analysis, vacancy rate estimation, maintenance budget (1-2% property value/year), and ROI calculation.
- PROPERTY MANAGEMENT BASICS: Include basics of tenant screening, lease agreements, maintenance scheduling, and landlord legal obligations.
- PROFESSIONAL REFERRAL: ALWAYS recommend consulting a real estate agent, mortgage broker, and notary for major decisions.
"""

    extra_calibration_hints = """
- Ask about current financial situation (savings, income, existing debts, credit score)
- Ask about target property type (house, apartment, rental investment, primary residence)
- Ask about preferred location and maximum budget
- Ask about desired timeline for purchase
- Ask about first-time buyer status
- Ask about any existing real estate experience or properties owned
"""


class RetirementProcessor(BasePlanProcessor):
    """Retirement planning, pensions, financial freedom, estate planning."""

    category = "retirement"
    display_name = "Retraite & Planification"

    domain_rules = """
- RETIREMENT CALCULATOR FIRST: Start by calculating retirement needs based on desired lifestyle, expected expenses, inflation, and life expectancy.
- PENSION RIGHTS RESEARCH: Include tasks for understanding all pension entitlements (government, employer, private, complementary).
- SOCIAL SECURITY OPTIMIZATION: Research optimal timing for pension claims. Understand trimestres, décote/surcote, and how to maximize lifetime benefits.
- INVESTMENT ALLOCATION BY AGE: Follow the 100-minus-age rule as a starting point for stock/bond allocation. Adjust based on risk tolerance and timeline.
- HEALTHCARE PLANNING: Include tasks for understanding healthcare costs in retirement, mutuelle senior, prévoyance, and long-term care (dépendance) options.
- ESTATE PLANNING BASICS: Include estate planning tasks (testament, donation, assurance-vie, démembrement, power of attorney, beneficiary designations).
- LIFESTYLE BUDGETING: Create a detailed retirement budget including housing, healthcare, travel, hobbies, and inflation adjustment (2-3% annually).
- PHASED RETIREMENT OPTIONS: Consider and plan for phased retirement (retraite progressive, part-time work, consulting, gradual transition).
- SOCIAL ACTIVITY PLANNING: Include tasks for planning social engagement, community involvement, and maintaining relationships post-retirement.
- SKILL DEVELOPMENT FOR HOBBIES: Include tasks for developing hobbies, skills, and interests to pursue in retirement — start BEFORE retiring.
- VOLUNTEER OPPORTUNITIES: Research volunteer roles that align with skills and interests for meaningful engagement.
- LIVING ARRANGEMENT RESEARCH: Include tasks for researching housing options (aging in place, downsizing, retirement communities, moving abroad).
- PROFESSIONAL REFERRAL: ALWAYS recommend consulting a certified financial planner or retirement-specific advisor.
"""

    extra_calibration_hints = """
- Ask about current age and target retirement age
- Ask about current retirement savings, investments, and pension entitlements
- Ask about desired retirement lifestyle, activities, and location
- Ask about existing financial obligations (mortgage, dependents, debts)
- Ask about health status and healthcare coverage
- Ask about family situation (spouse retirement, inheritance goals, dependents)
"""


class VolunteerProcessor(BasePlanProcessor):
    """Volunteering, humanitarian work, community service, social impact."""

    category = "volunteer"
    display_name = "Bénévolat & Impact Social"

    domain_rules = """
- CAUSE ALIGNMENT ASSESSMENT: Start by assessing personal values, passions, and causes that resonate most deeply. Match cause to motivation for sustained engagement.
- TIME COMMITMENT REALISTIC PLANNING: Plan realistic time commitments. Start small (2-4 hours/week) and increase gradually. Account for existing work/family obligations.
- ORGANIZATION RESEARCH: Include tasks for researching organizations (mission, reputation, financial transparency, impact metrics, reviews from volunteers).
- SKILLS MATCHING: Match existing professional and personal skills to volunteer roles. Include tasks for identifying transferable skills and areas for growth.
- TRAINING REQUIREMENTS: Research and complete any required training, certifications, background checks, or onboarding processes before starting.
- SAFETY BRIEFING: Include safety preparation tasks, especially for humanitarian, outdoor, disaster relief, or international volunteer work.
- CULTURAL SENSITIVITY: Include cultural awareness and sensitivity training for cross-cultural or international volunteer work.
- IMPACT MEASUREMENT: Include tasks for tracking personal contribution and impact (hours logged, people served, projects completed, outcomes achieved).
- BURNOUT PREVENTION: Schedule breaks and self-care. Include tasks for monitoring energy levels, setting healthy boundaries, and knowing when to step back.
- NETWORKING WITHIN SECTOR: Include tasks for connecting with other volunteers, mentors, NGO professionals, and sector networks.
- LEADERSHIP PROGRESSION: Plan a progression path from volunteer to team lead to project coordinator to board member if desired.
- DOCUMENTATION FOR RESUME: Include tasks for documenting experience, collecting references, and updating resume/LinkedIn with volunteer work.
"""

    extra_calibration_hints = """
- Ask about causes and social issues they care about most
- Ask about available time per week/month for volunteering
- Ask about relevant professional skills and experience
- Ask about preferred type of engagement (hands-on, administrative, remote, field work)
- Ask about geographic preferences (local community, national, international missions)
- Ask about previous volunteer or community service experience
"""


class SobrietyRecoveryProcessor(BasePlanProcessor):
    """Sobriety, addiction recovery, quitting smoking, substance management."""

    category = "sobriety"
    display_name = "Sobriété & Rétablissement"

    domain_rules = """
- ALWAYS RECOMMEND PROFESSIONAL SUPPORT: FIRST step must ALWAYS be connecting with professional support — therapist, counselor, addiction specialist, AA, NA, or medical professional. This plan supplements but NEVER replaces professional care.
- NEVER REPLACE MEDICAL ADVICE: Include clear disclaimers that this plan is a complementary tool, not a substitute for medical or psychological treatment.
- TRIGGER IDENTIFICATION: Include tasks for identifying personal triggers (people, places, emotions, times of day, situations) and creating specific avoidance and coping strategies for each.
- SUPPORT SYSTEM BUILDING: Include tasks for building a robust support network — sponsor, support group, trusted friends/family, therapist, crisis hotline numbers.
- ONE DAY AT A TIME: Structure the plan with daily focus. Short-term milestones matter more than long-term projections. Each day sober is a victory.
- HEALTHY REPLACEMENT ACTIVITIES: Include tasks for finding healthy replacement activities — exercise, creative hobbies, meditation, socializing, cooking, nature walks.
- ROUTINE RESTRUCTURING: Include tasks for building an entirely new daily routine that fills time previously occupied by substance use with positive activities.
- MILESTONE CELEBRATIONS: Plan meaningful non-substance celebrations at key milestones — 30, 60, 90, 180, and 365 days. Rewards that reinforce the new identity.
- RELAPSE PREVENTION PLAN: Include a detailed relapse prevention plan with warning signs, emergency contacts, immediate coping actions, and a "what to do if I slip" protocol.
- JOURNALING DAILY: Include daily journaling tasks for emotional processing, trigger tracking, gratitude practice, and progress reflection.
- PHYSICAL HEALTH RECOVERY: Include tasks for physical recovery — nutrition improvement, sleep hygiene, regular exercise, medical check-ups, hydration.
- SOCIAL SITUATION PREPARATION: Include tasks for preparing for social situations where substances may be present — scripts, exit strategies, bringing a supportive friend.
"""

    extra_calibration_hints = """
- Ask if they are currently working with a healthcare professional, counselor, or support group
- Ask about the specific substance or behavior they want to address (without judgment)
- Ask about previous recovery attempts and what helped or didn't
- Ask about their current support system (family, friends, groups)
- Ask about known triggers and highest-risk situations
- Ask about their physical health status and any medications
"""


class EnvironmentalProcessor(BasePlanProcessor):
    """Ecology, sustainable living, zero waste, carbon footprint reduction."""

    category = "environmental"
    display_name = "Écologie & Mode de Vie Durable"

    domain_rules = """
- CARBON FOOTPRINT ASSESSMENT FIRST: Start by assessing current carbon footprint using online calculators. Establish a baseline before making changes.
- ONE CHANGE AT A TIME: Do NOT plan to change everything at once. Introduce one sustainable habit every 1-2 weeks for lasting behavior change.
- COST SAVINGS TRACKING: Track financial savings alongside environmental impact. Many eco-changes save money — highlight this dual benefit for motivation.
- LOCAL COMMUNITY ENGAGEMENT: Include tasks for connecting with local environmental groups, farmers markets, community gardens, and repair cafés.
- SEASONAL EATING: Include tasks for learning seasonal and local food calendars, meal planning accordingly, and reducing food miles.
- WASTE AUDIT: Include a household waste audit task — track and categorize all waste for one week to identify the biggest reduction opportunities.
- TRANSPORTATION ALTERNATIVES: Include tasks for researching and testing alternative transportation — cycling, public transit, carpooling, walking, electric vehicles.
- ENERGY AUDIT: Include a home energy audit task — identify energy waste and plan efficiency improvements (insulation, LED, smart thermostat, renewable energy).
- WATER CONSERVATION: Include tasks for assessing and reducing water usage — low-flow fixtures, shorter showers, rainwater collection, garden irrigation.
- SUSTAINABLE SHOPPING GUIDE: Include tasks for developing sustainable shopping habits — buy less, buy quality, choose second-hand, local, and ethical brands.
- COMPOSTING: Include tasks for starting and maintaining a composting system appropriate to living situation (outdoor bin, vermicompost, bokashi).
- ADVOCACY AND EDUCATION: Include tasks for sharing knowledge with family/friends, participating in local environmental initiatives, and staying informed.
- PROGRESSIVE DIFFICULTY: Start with easy wins (reusable bags, water bottle, recycling) before harder lifestyle changes (diet shift, car-free living, home renovation).
"""

    extra_calibration_hints = """
- Ask about current lifestyle and living situation (urban/suburban/rural, house/apartment)
- Ask about which environmental areas they want to focus on first (food, transport, energy, waste, shopping)
- Ask about sustainable habits they already practice
- Ask about budget available for sustainable changes and investments
- Ask about household size and family willingness to participate
- Ask about primary motivation (climate concern, health benefits, cost savings, ethics, community)
"""


class MarathonEnduranceProcessor(BasePlanProcessor):
    """Marathon, half marathon, trail running, triathlon, endurance races."""

    category = "endurance"
    display_name = "Endurance & Courses"

    domain_rules = """
- BASE BUILDING PHASE: Start with 4-6 weeks of easy running to build aerobic base before any intensity work.
- PROGRESSIVE MILEAGE: Increase weekly mileage by maximum 10% per week. Never jump volume.
- LONG RUN: Schedule one long run per week. This is the cornerstone of endurance training.
- SPEED WORK AFTER BASE: Introduce intervals, tempo runs, and speed work ONLY after aerobic base is established.
- CROSS-TRAINING DAYS: Include 1-2 cross-training days per week (cycling, swimming, elliptical) to reduce injury risk.
- NUTRITION PLAN: Include race day fueling strategy — practice nutrition during long runs. Carb-loading protocol for race week.
- TAPER: Plan a 2-3 week taper before race day. Reduce volume by 40-60% while maintaining some intensity.
- RACE SIMULATION: Include at least 2 race-pace simulation runs in the last month before the event.
- GEAR TESTING: Test all gear (shoes, hydration vest, nutrition) during training — NOTHING new on race day.
- PACING STRATEGY: Define target pace zones (easy, tempo, race pace, interval). Include pacing practice runs.
- MENTAL TRAINING: Include visualization, mantras, and mental toughness exercises for race day suffering.
- RECOVERY PROTOCOLS: Include post-run recovery tasks (stretching, foam rolling, ice baths, rest days).
- RACE DAY CHECKLIST: Include a race day preparation task (logistics, gear check, warm-up routine, pacing plan).
"""

    extra_calibration_hints = """
- Ask about current running volume (km per week) and longest recent run
- Ask about race distance target and goal time
- Ask about running history and previous race experience
- Ask about past injuries (shin splints, IT band, plantar fasciitis)
- Ask about access to running routes, tracks, or trails
- Ask about current shoe type and equipment
"""


class MartialArtsProcessor(BasePlanProcessor):
    """Martial arts, boxing, MMA, karate, judo, BJJ, self-defense."""

    category = "martial_arts"
    display_name = "Arts Martiaux & Combat"

    domain_rules = """
- FIND QUALIFIED INSTRUCTOR: First task should ALWAYS be finding a qualified instructor/gym. Do NOT train combat sports alone as a beginner.
- FUNDAMENTALS OVER FLASH: Master basic stances, guards, and simple techniques before attempting advanced or flashy moves.
- FLEXIBILITY/MOBILITY FOUNDATION: Include daily flexibility and mobility work — essential for kicks, grappling, and injury prevention.
- PROGRESSIVE SPARRING: Introduce sparring gradually — shadow boxing → controlled drills → light sparring → full sparring over months.
- BELT/GRADE PROGRESSION: Set milestones around belt/grade promotions where applicable. Respect the timeline of the art.
- CROSS-TRAINING CONDITIONING: Include strength, cardio, and agility training alongside martial arts practice.
- INJURY PREVENTION: Include tasks for proper hand wrapping, mouthguard fitting, and protective gear acquisition.
- NUTRITION FOR TRAINING: Include nutrition tasks — proper fueling before/after training, weight management for competition classes.
- COMPETITION PREPARATION: If applicable, include competition-specific preparation (rules study, weight cut planning, mental prep).
- MENTAL DISCIPLINE: Include mental training tasks — focus, breathing, staying calm under pressure.
- RESPECT AND ETIQUETTE: Include dojo/gym etiquette learning — bowing, respect for partners, hygiene, proper attire.
- RECOVERY BETWEEN SESSIONS: Schedule adequate rest between hard sessions. Include active recovery and stretching.
"""

    extra_calibration_hints = """
- Ask about specific martial art interest (striking, grappling, mixed)
- Ask about current physical fitness level and flexibility
- Ask about goal (self-defense, competition, fitness, discipline)
- Ask about previous martial arts or combat sports experience
- Ask about access to gyms/dojos in their area
- Ask about any existing injuries or physical limitations
"""


class DanceProcessor(BasePlanProcessor):
    """Dance styles: salsa, bachata, ballet, hip hop, contemporary, ballroom."""

    category = "dance"
    display_name = "Danse"

    domain_rules = """
- WARM-UP AND COOL-DOWN: Every session must include a proper warm-up (joint mobilization, light cardio) and cool-down (stretching).
- MIRROR PRACTICE: Include regular mirror practice sessions for self-correction of posture, lines, and movement quality.
- MUSICALITY TRAINING: Include tasks for musicality development — listening to music, counting beats, understanding rhythm structures.
- BASIC STEPS MASTERY: Master basic steps and foundational movements before attempting combinations or choreography.
- VIDEO RECORDING: Include regular self-recording tasks for review — compare with reference videos to identify areas for improvement.
- CLASS ATTENDANCE: Plan a consistent class attendance schedule. Group classes for technique + social dancing for application.
- SOCIAL DANCE EVENTS: Include attendance at social dance events (milongas, socials, battles) for real-world practice from month 2.
- FLEXIBILITY WORK: Include daily flexibility and stretching routines — splits progression, back flexibility, hip opening.
- PERFORMANCE PREPARATION: If targeting a performance, include rehearsal schedule, run-throughs, and stage presence work.
- STYLE-SPECIFIC PROGRESSION: Follow the progression system of the style (salsa levels, ballet grades, belt system for capoeira).
- PARTNER DANCE ETIQUETTE: For partner dances, include lead/follow technique, floor craft, invitation etiquette.
- COSTUME/SHOE PREPARATION: Include tasks for acquiring proper dance shoes and attire for practice and performances.
"""

    extra_calibration_hints = """
- Ask about specific dance style interest
- Ask about current dance experience and level
- Ask about goal (social dancing, performance, competition, fitness)
- Ask about rhythm and musicality comfort level
- Ask about physical flexibility and fitness
- Ask about access to dance schools or social dance venues
"""


class OutdoorSurvivalProcessor(BasePlanProcessor):
    """Outdoor activities, survival skills, bushcraft, climbing, water sports."""

    category = "outdoor"
    display_name = "Plein Air & Survie"

    domain_rules = """
- SAFETY COURSE FIRST: First milestone should ALWAYS include taking a safety/survival basics course from qualified instructors.
- PROGRESSIVE DIFFICULTY: Progress from day hike → overnight camping → multi-day expedition. Never jump to advanced terrain.
- GEAR RESEARCH AND TESTING: Include gear research, acquisition, and testing tasks. Test ALL gear on short trips before committing to longer ones.
- NAVIGATION SKILLS: Include map reading, compass use, and GPS navigation training. Never rely on a single navigation method.
- WEATHER READING: Include weather interpretation skills — cloud reading, barometric pressure, storm signs.
- FIRST AID CERTIFICATION: Include getting wilderness first aid certified. Carry and know how to use a first aid kit.
- LEAVE NO TRACE: Include Leave No Trace principles — plan tasks around minimal environmental impact.
- PHYSICAL CONDITIONING: Include terrain-specific physical training (loaded hiking, swimming, climbing fitness) building up over weeks.
- WATER PURIFICATION: Include water sourcing and purification knowledge — filters, chemical treatment, boiling.
- EMERGENCY PROTOCOL: Include emergency planning tasks — emergency contacts, route sharing, PLB/satellite communicator.
- GROUP VS SOLO: Plan group experiences first before solo outings. Include tasks for developing solo judgment skills progressively.
- SEASONAL CONSIDERATIONS: Adapt the plan to seasons — cold weather gear, heat management, daylight hours, animal activity.
"""

    extra_calibration_hints = """
- Ask about specific outdoor activity interest (hiking, climbing, kayaking, bushcraft)
- Ask about current outdoor experience level
- Ask about physical fitness and any medical conditions
- Ask about gear they already own
- Ask about geographic region and typical terrain/weather
- Ask about solo or group preference
"""


class BodyTransformationProcessor(BasePlanProcessor):
    """Body recomposition, muscle gain, fat loss, physique transformation."""

    category = "body_transformation"
    display_name = "Transformation Physique"

    domain_rules = """
- BODY COMPOSITION ASSESSMENT: Start with body composition assessment (not just weight) — measurements, body fat estimate, photos.
- BEFORE PHOTOS/MEASUREMENTS: Include before photos and detailed body measurements as the FIRST task. Track progress visually.
- MACRO COUNTING BASICS: Include tasks to learn and practice macro counting (protein, carbs, fats). Calculate TDEE and set targets.
- PROGRESSIVE TRAINING PROGRAM: Structure training in 4-week blocks with progressive overload. Change stimulus periodically.
- DELOAD WEEKS: Include a deload week (reduced volume/intensity) every 4-6 weeks to prevent burnout and allow adaptation.
- SLEEP OPTIMIZATION: Include sleep optimization tasks — 7-9 hours is non-negotiable for body composition changes.
- SUPPLEMENT EDUCATION: Include evidence-based supplement education ONLY (creatine, protein, vitamin D). Warn against unproven supplements.
- MEAL PREP SCHEDULING: Include weekly meal prep tasks. Consistency in nutrition is the #1 factor for transformation.
- PROGRESS PHOTOS: Schedule progress photos biweekly under consistent conditions (same lighting, time, poses).
- STRENGTH BENCHMARKS: Track strength benchmarks alongside aesthetics — squat, bench, deadlift, pull-ups.
- BODY DYSMORPHIA AWARENESS: Include self-compassion tasks and realistic expectation setting. Warn against obsessive behaviors.
- SUSTAINABLE APPROACH: NO crash diets, no extreme caloric deficits. Maximum deficit of 500 kcal/day. Plan for long-term sustainability.
- MAINTENANCE PHASE PLANNING: Include a maintenance phase plan after the transformation — reverse dieting, new habits consolidation.
"""

    extra_calibration_hints = """
- Ask about current body composition (weight, approximate body fat, experience level)
- Ask about specific transformation goal (muscle gain, fat loss, recomposition)
- Ask about training history and current routine
- Ask about dietary habits and cooking ability
- Ask about access to gym equipment and facilities
- Ask about any history of eating disorders or body image issues
"""



class MentalHealthProcessor(BasePlanProcessor):
    """Anxiety, depression, therapy, burnout, stress management, self-esteem."""

    category = "mental_health"
    display_name = "Santé Mentale"

    domain_rules = """
- PROFESSIONAL THERAPIST FIRST: ALWAYS recommend consulting a professional therapist (psychologist, psychiatrist) as the very first step. This plan does NOT replace therapy.
- NEVER REPLACE THERAPY: This plan supplements professional care — it is NOT a substitute. Make this explicit in the plan introduction.
- CBT-INFORMED TECHNIQUES: Include thought records (identifying automatic thoughts, cognitive distortions, balanced alternatives) and behavioral activation (scheduling pleasant activities).
- PROGRESSIVE EXPOSURE: For anxiety-related goals, build a fear hierarchy and include gradual exposure tasks from least to most anxiety-provoking.
- MOOD TRACKING DAILY: Include a daily mood tracking task (1-10 scale + brief notes on triggers and context).
- SLEEP HYGIENE FOUNDATION: Address sleep as a prerequisite — include consistent sleep/wake times, screen reduction, wind-down routine.
- EXERCISE AS SUPPLEMENT: Include regular physical activity (walking, yoga, swimming) as a complementary tool — never as a replacement for therapy.
- SOCIAL CONNECTION MAINTENANCE: Include tasks to maintain or rebuild social connections — isolation worsens mental health.
- CRISIS PLAN: Include a crisis safety plan task (emergency contacts, crisis hotlines, warning signs, coping strategies).
- MEDICATION ADHERENCE: If the user mentions medication, include adherence tracking and regular check-ins with prescribing doctor.
- SELF-COMPASSION EXERCISES: Include self-compassion practices (self-kindness exercises, common humanity reflections, mindful awareness).
- STRESS MANAGEMENT TECHNIQUES: Include concrete techniques (box breathing, progressive muscle relaxation, grounding exercises, journaling).
- SETBACK NORMALIZATION: Explicitly plan for setbacks — normalize them as part of recovery, not failure. Include "bad day" protocols.
"""

    extra_calibration_hints = """
- Ask if they are currently seeing a therapist or mental health professional
- Ask about specific symptoms or challenges they're experiencing
- Ask about their support system (friends, family, partner)
- Ask about any current medication or treatment
- Ask about sleep quality and daily routines
- Ask about previous therapy or mental health support experience
"""


class SleepOptimizationProcessor(BasePlanProcessor):
    """Sleep improvement, insomnia, circadian rhythm, energy management."""

    category = "sleep"
    display_name = "Sommeil & Récupération"

    domain_rules = """
- SLEEP DIARY FIRST: Start with a 2-week sleep diary (bedtime, wake time, sleep latency, awakenings, sleep quality rating) before making any changes.
- CONSISTENT WAKE TIME: The single most important rule — set a consistent wake time 7 days/week. This anchors the circadian rhythm. Prioritize this over bedtime.
- BEDROOM ENVIRONMENT: Include tasks to optimize the sleep environment — dark (blackout curtains or sleep mask), cool (18-20°C), quiet (earplugs or white noise).
- SCREEN CURFEW: Enforce a 1-hour screen curfew before bed. Include alternative activities (reading, stretching, journaling).
- CAFFEINE CUTOFF: No caffeine after 2 PM. Include a task to identify all caffeine sources (coffee, tea, chocolate, energy drinks, medications).
- EXERCISE TIMING: Include regular exercise but NOT within 3 hours of bedtime. Morning or afternoon exercise is optimal for sleep.
- WIND-DOWN ROUTINE: Build a consistent 30-60 minute wind-down routine (dim lights, relaxation activities, preparation for bed).
- CBT-I TECHNIQUES: Include cognitive behavioral techniques for insomnia — stimulus control (bed only for sleep), sleep restriction therapy (with medical guidance), cognitive restructuring of sleep anxiety.
- SLEEP RESTRICTION: If chronic insomnia, include sleep restriction protocol (reducing time in bed to match actual sleep time, then gradually increasing). ALWAYS recommend medical guidance for this.
- NAP PROTOCOLS: If napping, limit to 20-30 minutes before 3 PM. For severe insomnia, eliminate naps initially.
- CIRCADIAN RHYTHM ALIGNMENT: Include morning light exposure (15-30 min within 1 hour of waking) and evening light reduction.
"""

    extra_calibration_hints = """
- Ask about current sleep schedule (bedtime, wake time, weekday vs weekend)
- Ask about specific sleep problems (falling asleep, staying asleep, waking too early, poor quality)
- Ask about caffeine, alcohol, and screen habits
- Ask about bedroom environment (light, noise, temperature, bed partner)
- Ask about stress levels and mental health
- Ask about any sleep-related medical conditions or medications
"""


class HealthyAgingProcessor(BasePlanProcessor):
    """Longevity, senior wellness, cognitive health, mobility, retirement lifestyle."""

    category = "aging"
    display_name = "Bien Vieillir"

    domain_rules = """
- MEDICAL CHECKUP SCHEDULE: Include a regular medical checkup schedule (annual physical, dental, vision, hearing, bone density, cancer screenings as age-appropriate).
- BALANCE AND FALL PREVENTION: Include balance exercises (single-leg stands, heel-to-toe walking, tai chi) and fall risk assessment tasks. Falls are the #1 injury risk.
- COGNITIVE EXERCISES: Include daily cognitive stimulation — puzzles, learning new skills, reading, social interaction. Variety matters more than intensity.
- NUTRITION ADAPTATION: Adjust nutrition for aging — protein needs increase (1.0-1.2g/kg/day), calcium and vitamin D supplementation, hydration monitoring.
- SOCIAL CONNECTION MAINTENANCE: Include regular social engagement tasks — isolation is a major health risk for older adults. Plan calls, visits, group activities, volunteering.
- TECHNOLOGY LITERACY: Include tasks to learn and maintain technology skills for independence — smartphone, video calls, online banking, telehealth.
- FINANCIAL PLANNING REVIEW: Include tasks to review financial plans — retirement funds, estate planning, insurance coverage, power of attorney updates.
- LEGAL DOCUMENTS: Include tasks to prepare or update essential documents — will, living will, power of attorney, healthcare proxy.
- MOBILITY MAINTENANCE: Include daily walking (30+ minutes), stretching, and strength exercises. Consistency is key — even light movement daily matters.
- PURPOSE AND MEANING: Include activities that provide purpose — volunteering, mentoring, community involvement, learning, creative projects.
- LEGACY PROJECTS: Include tasks related to legacy — memoir writing, photo organization, family history recording, skill sharing with younger generations.
"""

    extra_calibration_hints = """
- Ask about current age and general health status
- Ask about mobility and physical activity level
- Ask about social connections and living situation (alone, with partner, near family)
- Ask about specific health concerns or chronic conditions
- Ask about current hobbies and interests
- Ask about retirement status and daily routine
"""


class WeightManagementProcessor(BasePlanProcessor):
    """Weight loss, weight gain, body composition, nutrition planning."""

    category = "weight_management"
    display_name = "Gestion du Poids"

    domain_rules = """
- MEDICAL CHECKUP FIRST: ALWAYS recommend a medical checkup before starting any weight management plan. Include blood work and metabolic assessment.
- REALISTIC GOALS: Set realistic targets — 0.5-1 kg/week for weight loss, 0.25-0.5 kg/week for weight gain. Set milestones accordingly.
- CALORIE COUNTING EDUCATION: Teach calorie awareness and tracking as a temporary educational tool — not as an obsessive long-term practice. Include tasks to learn portion sizes.
- MEAL PLANNING AND PREP: Include weekly meal planning and prep tasks. Preparation is the foundation of dietary consistency.
- EMOTIONAL EATING AWARENESS: Include tasks to identify emotional eating triggers and develop alternative coping strategies (journaling, walking, calling a friend).
- HUNGER/FULLNESS SCALE: Teach the 1-10 hunger/fullness scale. Include daily practice of eating mindfully and rating hunger before and after meals.
- PROGRESSIVE EXERCISE: Incorporate exercise gradually — start with walking, add strength training, then increase intensity. Never start with extreme routines.
- BODY COMPOSITION OVER SCALE: Emphasize body composition (muscle vs fat) over scale weight. Include measurements (waist, hips, arms) alongside weight.
- WEEKLY MEASUREMENTS: Include weekly weigh-ins (same day, same time, same conditions) and monthly measurements. Track trends, not daily fluctuations.
- PLATEAU MANAGEMENT: Plan for plateaus — include diet breaks (1-2 weeks at maintenance) and refeed days. Plateaus are normal after 4-8 weeks.
- MAINTENANCE PHASE: The maintenance phase is the MOST important part of the plan. Dedicate the final 25-30% of the plan to maintaining results and building sustainable habits.
- SUSTAINABLE APPROACH ONLY: Only support sustainable, evidence-based approaches. No crash diets, no extreme restriction, no "detox" plans.
- PROFESSIONAL REFERRAL FOR EATING DISORDERS: If user shows signs of disordered eating (extreme restriction, binge-purge, body dysmorphia), ALWAYS include immediate referral to eating disorder specialist.
"""

    extra_calibration_hints = """
- Ask about current weight, height, and goal weight
- Ask about previous weight management attempts (what worked, what didn't)
- Ask about current eating habits and relationship with food
- Ask about physical activity level and preferences
- Ask about any medical conditions or medications that affect weight
- Ask about emotional relationship with food and body image
"""


class FertilityPregnancyProcessor(BasePlanProcessor):
    """Fertility, conception, pregnancy, prenatal care, birth preparation."""

    category = "fertility"
    display_name = "Fertilité & Grossesse"

    domain_rules = """
- OB/GYN FIRST: ALWAYS recommend consulting an OB/GYN or reproductive specialist as the very first step. This plan supplements medical care.
- PRECONCEPTION HEALTH: Include tasks for preconception health optimization — medical checkup, dental visit, medication review, BMI assessment.
- NUTRITION: Include prenatal nutrition tasks — folate supplementation (at least 400mcg daily, ideally 3 months before conception), iron-rich foods, calcium intake, adequate protein, hydration.
- LIFESTYLE MODIFICATIONS: Include tasks for lifestyle changes — alcohol cessation, caffeine reduction (max 200mg/day), smoking cessation, environmental toxin awareness.
- STRESS MANAGEMENT: Include stress reduction techniques — fertility journeys are emotionally taxing. Plan meditation, gentle exercise, support groups, journaling.
- EXERCISE GUIDELINES: Include moderate exercise (walking, swimming, prenatal yoga) and avoid overheating. Adjust intensity per trimester and medical guidance.
- MEDICAL APPOINTMENTS SCHEDULE: Include a complete medical appointment schedule — preconception checkup, prenatal visits (monthly → biweekly → weekly), screenings, ultrasounds.
- BIRTH PLAN PREPARATION: Include tasks to research and prepare a birth plan — preferences for labor, pain management, delivery, and immediate postpartum.
- PARTNER INVOLVEMENT: Include tasks for partner participation — attending appointments, birth preparation classes, emotional support, shared decision-making.
- FINANCIAL PLANNING: Include financial preparation tasks — parental leave planning, baby budget (gear, childcare), insurance review, savings goal.
- HOME PREPARATION: Include home preparation tasks — nursery setup, baby-proofing timeline, essential gear research and acquisition.
- POSTPARTUM PLANNING: Include postpartum preparation — meal prep/freezing, support network setup, postpartum recovery plan, breastfeeding resources.
- MENTAL HEALTH MONITORING: Include regular mental health check-ins throughout the journey — fertility struggles, prenatal anxiety/depression, and postpartum mood monitoring.
"""

    extra_calibration_hints = """
- Ask about current stage (trying to conceive, undergoing treatment, currently pregnant, postpartum)
- Ask about any fertility challenges or treatments
- Ask about current health and lifestyle habits
- Ask about partner situation and involvement
- Ask about previous pregnancies or fertility experiences
- Ask about emotional state and support system
"""



class MusicProductionProcessor(BasePlanProcessor):
    """Beatmaking, mixing, mastering, music release, DAW workflow."""

    category = "music_production"
    display_name = "Production Musicale"

    domain_rules = """
- DAW MASTERY FIRST: Start by learning the chosen DAW (Ableton, FL Studio, Logic Pro) fundamentals — navigation, shortcuts, workflow.
- SOUND DESIGN BASICS: Learn synthesis basics (oscillators, filters, envelopes, LFOs) before using only presets.
- MIXING FUNDAMENTALS: Teach EQ (frequency carving, high-pass filters), compression (ratio, threshold, attack/release), and reverb (space, depth) progressively.
- ARRANGEMENT STRUCTURE: Study song structure (intro, verse, chorus, bridge, drop, outro) with reference tracks before creating original arrangements.
- REFERENCE TRACKS STUDY: Include regular tasks to analyze reference tracks (EQ balance, stereo image, dynamics, arrangement) in the target genre.
- EAR TRAINING DAILY: Include 10-15 min daily ear training exercises (frequency identification, compression detection, stereo placement).
- COLLABORATION NETWORKING: Include tasks to connect with other producers, vocalists, and artists for collaboration and feedback.
- SAMPLE LIBRARY BUILDING: Organize and curate a personal sample library — include tasks for sound selection, categorization, and original sample creation.
- RELEASE STRATEGY: Plan distribution (DistroKid, TuneCore, LANDR), promotion (social media, playlists, blogs), and timeline for releases.
- COPYRIGHT & LICENSING: Include tasks to understand music copyright, royalties, sample clearance, and licensing basics (SACEM, BMI/ASCAP).
"""

    extra_calibration_hints = """
- Ask about current DAW and experience level
- Ask about target genre or style of music
- Ask about available equipment (monitors, headphones, MIDI controller, audio interface)
- Ask about goal (release music, produce for others, hobby, career change)
- Ask about musical background (instrument, theory knowledge)
- Ask about budget for plugins, samples, and equipment
"""


class CreativeWritingProcessor(BasePlanProcessor):
    """Writing books, novels, poetry, screenplays, blogs, publishing."""

    category = "writing"
    display_name = "\u00c9criture & Publication"

    domain_rules = """
- DAILY WORD COUNT TARGETS: Set specific daily word count goals (500-2000 words depending on level) and track consistently.
- OUTLINE BEFORE DRAFTING: Create a detailed outline (plot beats, chapter summaries, character arcs) before starting the first draft.
- FIRST DRAFT = NO EDITING: Write the first draft without going back to edit. Momentum over perfection. Silence the inner critic.
- REVISION CYCLES: Plan distinct revision passes — structure/plot → scene pacing → prose quality → line editing → final polish.
- BETA READERS FEEDBACK: Include tasks to find and work with beta readers after second draft. Plan for incorporating feedback.
- GENRE CONVENTIONS STUDY: Include tasks to read widely in the target genre and analyze what works (structure, tropes, reader expectations).
- CHARACTER DEVELOPMENT EXERCISES: Include character sheets, backstory writing, dialogue exercises, and motivation mapping tasks.
- WORLD-BUILDING FOR FICTION: For fiction, include dedicated world-building tasks (setting, rules, history, culture) before or during outlining.
- QUERY LETTER FOR PUBLISHING: If targeting traditional publishing, include query letter drafting, agent research, and submission tracking tasks.
- SELF-PUBLISHING WORKFLOW: If self-publishing, include tasks for cover design, formatting (ebook + print), ISBN, and platform setup (Amazon KDP, Kobo, etc.).
- MARKETING PLATFORM: Include author platform building tasks (website, social media, newsletter, reader community) starting early in the process.
"""

    extra_calibration_hints = """
- Ask about the type of writing (novel, poetry, screenplay, blog, non-fiction)
- Ask about current writing habits and experience
- Ask about target audience and genre
- Ask about publishing goal (traditional, self-publishing, personal)
- Ask about time available for writing daily/weekly
- Ask about any writing they've already completed (drafts, outlines, short stories)
"""


class FashionStyleProcessor(BasePlanProcessor):
    """Personal style, wardrobe building, fashion design, image consulting."""

    category = "fashion"
    display_name = "Mode & Style"

    domain_rules = """
- WARDROBE AUDIT FIRST: Start with a complete wardrobe audit — inventory every piece, identify gaps, remove items that don't fit or serve.
- CAPSULE WARDROBE BUILDING: Build a capsule wardrobe with versatile, mix-and-match pieces before adding statement items.
- COLOR PALETTE IDENTIFICATION: Include tasks to identify personal color palette (warm/cool, seasonal analysis) for cohesive styling.
- BODY TYPE UNDERSTANDING: Include tasks to understand body proportions and silhouettes that enhance the wearer's figure.
- QUALITY OVER QUANTITY: Prioritize fewer, better-quality pieces over fast fashion. Include fabric and construction quality assessment tasks.
- BUDGET PER CATEGORY: Set a realistic budget allocated per clothing category (tops, bottoms, outerwear, shoes, accessories).
- SEASONAL PLANNING: Plan wardrobe updates seasonally — include tasks for transitional pieces and layering strategies.
- ALTERATIONS & TAILORING SKILLS: Include tasks to learn basic alterations (hemming, taking in seams) and when to use a professional tailor.
- SUSTAINABLE FASHION: Include tasks about sustainable shopping practices (second-hand, ethical brands, capsule approach, clothing care).
- PERSONAL BRAND CONSISTENCY: Ensure style choices align with personal and professional image goals — include mood board creation.
- TREND VS CLASSIC BALANCE: Teach the balance between incorporating trends and investing in timeless classics. Max 20% trend pieces.
"""

    extra_calibration_hints = """
- Ask about current wardrobe satisfaction and pain points
- Ask about style inspirations and references (people, brands, aesthetics)
- Ask about budget available for wardrobe building
- Ask about lifestyle needs (work dress code, casual, events, climate)
- Ask about body confidence and any specific concerns
- Ask about shopping habits (frequency, online vs in-store, impulse vs planned)
"""


class PublicSpeakingProcessor(BasePlanProcessor):
    """Presentations, speeches, conferences, pitches, communication skills."""

    category = "public_speaking"
    display_name = "Prise de Parole & Communication"

    domain_rules = """
- PROGRESSIVE EXPOSURE: Start with mirror practice \u2192 camera recording \u2192 small group (3-5 people) \u2192 medium group (10-20) \u2192 large audience. Never skip steps.
- SPEECH STRUCTURE: Teach the structure — hook (grab attention) \u2192 story (engage emotionally) \u2192 point (deliver the message) \u2192 call to action (motivate).
- VOCAL EXERCISES: Include daily vocal exercises — breathing (diaphragmatic), projection, pace variation, articulation drills, and pause mastery.
- BODY LANGUAGE PRACTICE: Include tasks on posture, eye contact, hand gestures, stage movement, and facial expressions. Record and review.
- FILLER WORD ELIMINATION: Include specific exercises to identify and reduce filler words ("euh", "um", "donc", "voil\u00e0"). Use recording for self-analysis.
- Q&A PREPARATION: For every speech/presentation, include a task to anticipate questions and prepare confident, concise answers.
- SLIDE DESIGN PRINCIPLES: Teach minimal slide design (1 idea per slide, visual > text, consistent branding, maximum 6 words per slide).
- STORYTELLING TECHNIQUES: Include tasks to practice storytelling frameworks (hero's journey, problem-solution, before-after, three-act structure).
- AUDIENCE ANALYSIS: Before every speaking engagement, include audience research (who are they, what do they need, what's their level).
- FEEDBACK RECORDING & REVIEW: Record every practice session and real speech. Include dedicated review tasks to identify improvement areas.
- TOASTMASTERS RECOMMENDATION: Recommend joining Toastmasters or a similar public speaking club for regular practice and structured feedback.
"""

    extra_calibration_hints = """
- Ask about current comfort level with speaking in front of people
- Ask about specific speaking goals (work presentations, conferences, TEDx, pitch)
- Ask about past speaking experiences (positive and negative)
- Ask about any specific fears (forgetting words, judgment, shaking voice)
- Ask about upcoming speaking opportunities or deadlines
- Ask about preferred language for speaking (French, English, bilingual)
"""


class ContentCreationProcessor(BasePlanProcessor):
    """Social media, YouTube, podcasting, blogging, influencing, monetization."""

    category = "content_creation"
    display_name = "Création de Contenu"

    domain_rules = """
- NICHE DEFINITION FIRST: Start by defining a clear, specific niche — intersection of passion, expertise, and audience demand. Do NOT try to cover everything.
- CONTENT CALENDAR WEEKLY: Create a weekly content calendar with specific topics, formats, and posting times. Plan at least 2 weeks ahead.
- PLATFORM-SPECIFIC OPTIMIZATION: Tailor content format, length, and style to each platform (vertical video for TikTok/Reels, long-form for YouTube, threads for Twitter).
- SEO BASICS: Include tasks to learn SEO fundamentals — keyword research, titles, descriptions, tags, thumbnails (YouTube), hashtags (social).
- ANALYTICS TRACKING: Include weekly tasks to review analytics (views, engagement rate, retention, growth) and adjust strategy based on data.
- ENGAGEMENT OVER FOLLOWERS: Focus on community building and engagement metrics over vanity follower counts. Include tasks for replying to comments and DMs.
- BATCH CONTENT CREATION: Teach batch creation — film/write multiple pieces in one session, edit in another, schedule in advance.
- REPURPOSING CONTENT: Include tasks to repurpose one piece of content across multiple platforms (video \u2192 short clips \u2192 blog post \u2192 carousel \u2192 newsletter).
- EQUIPMENT PROGRESSION: Start with phone and natural light. Upgrade equipment only after proving consistency (3+ months). Include specific upgrade milestones.
- CONSISTENCY SCHEDULE: Define a sustainable posting frequency and stick to it. Consistency > frequency. Better 2x/week reliably than daily for 2 weeks then nothing.
- COLLABORATION STRATEGY: Include tasks to identify and reach out to creators in similar niches for collaborations, cross-promotions, and guest appearances.
- MONETIZATION MILESTONES: Plan monetization progressively — first 100 followers, first 1K, first brand deal, first product. Do NOT monetize before providing value.
"""

    extra_calibration_hints = """
- Ask about target platform(s) and content format preference (video, writing, audio)
- Ask about niche or topic area they want to cover
- Ask about current audience size and online presence
- Ask about available time for content creation per week
- Ask about equipment they already have (camera, mic, editing software)
- Ask about goal (personal brand, side income, full-time creator, business marketing)
"""

class MinimalismProcessor(BasePlanProcessor):
    """Minimalism, decluttering, simplifying life, capsule wardrobe."""

    category = "minimalism"
    display_name = "Minimalisme & Simplicité"

    domain_rules = """
- ROOM-BY-ROOM DECLUTTERING: Tackle one room or zone at a time — never the whole house at once. Complete one space before moving on.
- KEEP/DONATE/DISCARD METHOD: For every item, decide: keep, donate, or discard. Include specific tasks for each decision category.
- SENTIMENTAL ITEMS LAST: Start with easy categories (duplicates, expired items, obvious trash) and save sentimental items for the final phase.
- ONE-IN-ONE-OUT RULE: Once decluttered, enforce a strict rule — for every new item brought in, one must leave.
- DIGITAL DECLUTTERING: Include tasks for email unsubscribe, app audit, photo cleanup, file organization, and digital account consolidation.
- CAPSULE WARDROBE: Include a milestone for building a capsule wardrobe — 30-40 versatile pieces that mix and match.
- SUBSCRIPTION AUDIT: Include a task to audit and cancel unused subscriptions (streaming, apps, magazines, memberships).
- FINANCIAL SIMPLIFICATION: Include tasks for consolidating bank accounts, automating bills, and simplifying financial systems.
- TIME AUDIT: Include a task to track how time is spent for 1 week, then eliminate or delegate low-value activities.
- ENERGY MANAGEMENT: Include tasks for identifying energy drains (commitments, relationships, habits) and creating boundaries.
- SAYING NO PRACTICE: Include progressive exercises in declining requests and commitments that don't align with priorities.
- QUALITY OVER QUANTITY: Include a purchasing guide — wait 48h before buying, focus on durability and multi-function items.
- MAINTENANCE ROUTINES: Include daily 10-min tidy, weekly zone review, and monthly deep assessment routines.
"""

    extra_calibration_hints = """
- Ask about current living space size and clutter level
- Ask about what areas feel most overwhelming
- Ask about previous decluttering attempts (what worked, what failed)
- Ask about emotional attachment to possessions
- Ask about household members and their willingness to participate
- Ask about specific minimalism goals (space, finances, time, mental clarity)
"""


class DigitalDetoxProcessor(BasePlanProcessor):
    """Digital detox, screen time reduction, tech-life balance."""

    category = "digital_detox"
    display_name = "Détox Digitale & Tech Balance"

    domain_rules = """
- SCREEN TIME AUDIT FIRST: Start with 1 week of tracking actual screen time using built-in tools (Screen Time, Digital Wellbeing). Base all goals on real data.
- PROGRESSIVE REDUCTION: Reduce screen time gradually (15-30 min less per week) — never go cold turkey, which leads to relapse.
- NOTIFICATION AUDIT AND CULL: Include a task to disable non-essential notifications. Keep only calls, messages from close contacts, and calendar.
- PHONE-FREE ZONES/TIMES: Establish specific no-phone zones (bedroom, dining table) and times (first hour after waking, last hour before bed).
- REPLACEMENT ACTIVITIES: For every digital habit removed, plan a specific analog replacement (scrolling → reading, gaming → board games, etc.).
- SOCIAL MEDIA STRATEGIES: Include platform-specific reduction strategies — unfollow, mute, time limits, feed curation, or account deletion.
- EMAIL BATCHING: Include a task to set up email batching — check email 2-3 times per day at set times, not continuously.
- APP LIMITS SETUP: Include tasks for configuring app timers, grayscale mode, removing apps from home screen, and using website blockers.
- ANALOG ALTERNATIVES: Include tasks to acquire analog alternatives for digital habits (physical books, paper notebook, alarm clock, watch).
- BOREDOM TOLERANCE BUILDING: Include progressive exercises in sitting with boredom without reaching for a device (start with 5 min, build up).
- SLEEP DEVICE PROTOCOL: Include a strict no-screens-30-min-before-bed rule with a device charging station outside the bedroom.
- BOUNDARY COMMUNICATION: Include tasks to inform family, friends, and colleagues about new digital boundaries and availability windows.
"""

    extra_calibration_hints = """
- Ask about current daily screen time (actual data if available)
- Ask about which apps/platforms consume the most time
- Ask about what triggers excessive phone use (boredom, anxiety, habit)
- Ask about previous attempts to reduce screen time
- Ask about work requirements for screen use (separate work vs personal)
- Ask about sleep quality and device use before bed
"""


class HomeOrganizationProcessor(BasePlanProcessor):
    """Home organization, productivity systems, cleaning routines, planning."""

    category = "organization"
    display_name = "Organisation & Productivité Maison"

    domain_rules = """
- ONE ZONE PER WEEK: Tackle one zone or category at a time — never the whole house simultaneously. Complete each zone before moving on.
- CATEGORIZE BEFORE BUYING CONTAINERS: Sort and declutter items first. Only buy storage solutions after knowing exactly what needs to be stored.
- LABELING SYSTEM: Include tasks for implementing a consistent labeling system — use a label maker or uniform labels for all storage.
- MAINTENANCE ROUTINES: Build a tiered routine — 5-minute daily tidying, 30-minute weekly zone reset, and monthly deep organization check.
- PAPER MANAGEMENT: Include a paper system — scan important documents, shred unneeded papers, set up a simple filing system (action, reference, archive).
- DIGITAL FILE ORGANIZATION: Include tasks for organizing digital files — consistent folder structure, naming conventions, cloud backup, and regular cleanup.
- MEAL PLANNING SYSTEM: Include weekly meal planning, grocery list automation, pantry inventory, and batch cooking scheduling.
- CLEANING SCHEDULE: Create a rotating cleaning schedule — daily quick tasks, weekly deep tasks per zone, monthly and seasonal tasks.
- SEASONAL ROTATION: Include tasks for seasonal item rotation (clothes, decorations, sports equipment) with labeled storage.
- FAMILY INVOLVEMENT: Include tasks for assigning age-appropriate responsibilities and creating shared family organization systems.
- BEFORE/AFTER DOCUMENTATION: Include tasks to photograph spaces before and after organizing for motivation and maintenance reference.
- BUYING GUIDE: Include research tasks for storage solutions — measure spaces first, prefer uniform containers, prioritize clear/labeled systems.
"""

    extra_calibration_hints = """
- Ask about which areas of the home need the most organization
- Ask about household size and who lives there
- Ask about current organizational systems (what exists, what fails)
- Ask about time available for organizing and maintenance
- Ask about budget for organizational supplies and storage
- Ask about specific pain points (always losing keys, cluttered kitchen, paper piles)
"""


class EmigrationProcessor(BasePlanProcessor):
    """Emigration, immigration, expatriation, moving abroad."""

    category = "emigration"
    display_name = "Expatriation & Immigration"

    domain_rules = """
- VISA/PERMIT RESEARCH FIRST: First milestone must be thorough research on visa types, eligibility requirements, processing times, and costs for the target country.
- LANGUAGE PREPARATION: Include language learning tasks appropriate to the destination — minimum A2 level before arrival for non-English countries.
- COST OF LIVING COMPARISON: Include a detailed task comparing cost of living (housing, food, transport, healthcare, taxes) between current and target country.
- JOB MARKET RESEARCH: Include tasks for researching job market, salary expectations, CV/resume adaptation to local format, and professional network building.
- HOUSING RESEARCH: Include tasks for understanding the rental market, temporary accommodation for arrival, and lease requirements in the target country.
- HEALTHCARE SYSTEM: Include tasks for understanding the target country's healthcare system, required insurance, and transferring medical records.
- BANKING SETUP: Include tasks for researching banking options, opening an account (some can be done remotely), and understanding the financial system.
- CULTURAL ADAPTATION: Include tasks for studying cultural norms, workplace culture, social customs, and daily life expectations.
- SOCIAL NETWORK BUILDING: Include tasks for joining expat communities, local meetups, professional groups, and social platforms popular in the target country.
- DOCUMENT PREPARATION: Include tasks for document translation, apostille, notarization, and creating certified copies of all important documents.
- MOVING LOGISTICS TIMELINE: Include a detailed timeline for shipping belongings, selling/storing items, and coordinating the physical move.
- TAX IMPLICATIONS: Include tasks for understanding tax obligations in BOTH countries — exit taxes, double taxation treaties, and ongoing filing requirements.
- EMERGENCY PLAN: Include tasks for establishing local emergency contacts, embassy registration, and a contingency plan if things don't work out.
- HOMESICKNESS MANAGEMENT: Include tasks for maintaining connections with home (regular calls, visits budget) and building local routines for emotional grounding.
"""

    extra_calibration_hints = """
- Ask about the target country and city
- Ask about the reason for emigrating (work, study, family, lifestyle)
- Ask about current visa/residency status and nationality
- Ask about language skills in the target country's language
- Ask about timeline constraints (job start date, lease end, family situation)
- Ask about whether they're moving alone or with family/partner
"""


class EventPlanningProcessor(BasePlanProcessor):
    """Event planning, weddings, parties, ceremonies, galas."""

    category = "event_planning"
    display_name = "Organisation d'Événements"

    domain_rules = """
- PURPOSE AND AUDIENCE FIRST: First task must define the event's purpose, target audience, expected attendance, and overall vision/theme.
- BUDGET BREAKDOWN: Include a detailed budget broken down by category (venue, catering, decoration, entertainment, photography, invitations, contingency).
- VENUE SELECTION CRITERIA: Include tasks for venue research with specific criteria (capacity, location, accessibility, parking, catering options, backup indoor space).
- VENDOR COMPARISON: Include tasks for getting multiple quotes (minimum 3) for each major vendor, checking reviews, and confirming availability.
- TIMELINE WORKING BACKWARDS: Build the entire plan working backwards from the event date — book venue 6-12 months ahead, vendors 3-6 months, invitations 6-8 weeks.
- GUEST LIST MANAGEMENT: Include tasks for creating and managing the guest list, tracking RSVPs, dietary restrictions, and special accommodations.
- INVITATION DESIGN AND SENDING: Include tasks for designing, printing/sending invitations with RSVP deadline, and follow-up with non-respondents.
- MENU/CATERING PLANNING: Include tasks for menu selection, tasting appointments, dietary accommodation planning, and final headcount confirmation.
- DECORATION THEME: Include tasks for developing a cohesive decoration theme, sourcing materials, and planning setup logistics.
- ENTERTAINMENT BOOKING: Include tasks for researching and booking entertainment (DJ, band, speakers, activities) with contract review.
- DAY-OF SCHEDULE: Include a minute-by-minute day-of schedule with assigned responsibilities for each team member or helper.
- CONTINGENCY PLANS: Include backup plans for key risks — weather (outdoor events), vendor no-shows, technical failures, and over/under attendance.
- POST-EVENT FOLLOW-UP: Include tasks for thank-you notes, vendor reviews, photo/video collection, and financial reconciliation.
"""

    extra_calibration_hints = """
- Ask about the type of event (wedding, birthday, corporate, gala, etc.)
- Ask about expected number of guests
- Ask about total budget available
- Ask about the event date and whether venue is already booked
- Ask about whether they have a planner/coordinator or doing it themselves
- Ask about any cultural or religious requirements for the event
"""




class SocialMediaGrowthProcessor(BasePlanProcessor):
    """Instagram, TikTok, YouTube, LinkedIn growth and personal branding."""

    category = "social_media"
    display_name = "Croissance Réseaux Sociaux"

    domain_rules = """
- PLATFORM FOCUS: Choose 1-2 platforms MAX — don't spread thin. Master one before expanding.
- CONTENT PILLARS: Define 3-5 content themes/pillars that align with brand and audience. Every post should fit a pillar.
- CONSISTENCY OVER FREQUENCY: A sustainable posting schedule (3-5x/week) beats daily burnout. Include a content calendar task.
- ENGAGEMENT > FOLLOWERS: Prioritize engagement rate (comments, shares, saves) over vanity follower count. Track engagement weekly.
- ANALYTICS REVIEW: Include a weekly analytics review task — identify top-performing content and double down.
- HASHTAG STRATEGY: Include tasks for hashtag research (mix of niche, medium, and broad hashtags). Update hashtag sets monthly.
- COLLABORATION STRATEGY: Include tasks for finding and reaching out to collaborators (duets, collabs, guest posts) from month 2 onwards.
- CONTENT BATCHING: Create content in weekly batches (film/write/design in one session, schedule across the week).
- REPURPOSE CONTENT: Include tasks to repurpose content across platforms (TikTok → Reels → Shorts, thread → carousel, etc.)
- COMMUNITY MANAGEMENT: Include daily 15-30 min tasks for responding to comments, DMs, and engaging with others’ content.
- BRAND VOICE: Include tasks early on to define brand voice, visual identity, and bio optimization.
- MONETIZATION MILESTONES: Set milestones at 1K, 10K, and 100K followers with corresponding monetization strategies (brand deals, affiliate, products).
- ALGORITHM UNDERSTANDING: Include tasks to study and stay updated on platform-specific algorithm changes.
"""

    extra_calibration_hints = """
- Ask about which platform(s) they want to focus on
- Ask about current follower count and engagement rate
- Ask about their niche or topic area
- Ask about content creation skills (video editing, photography, writing)
- Ask about time available for content creation per week
- Ask about monetization goals (hobby, side income, full-time)
"""


class PodcastProcessor(BasePlanProcessor):
    """Launching, producing, and growing a podcast."""

    category = "podcast"
    display_name = "Podcast"

    domain_rules = """
- CONCEPT BEFORE EQUIPMENT: Define concept, niche, target audience, and unique angle BEFORE buying any equipment.
- PILOT EPISODES: Record 3 pilot episodes before official launch to refine format, test audio quality, and build confidence.
- LAUNCH WITH BATCH: Launch with 3+ episodes available so new listeners can binge and subscribe.
- RECORDING WORKFLOW: Optimize recording workflow early (quiet space, consistent setup, pre-recording checklist, post-recording routine).
- EDITING SKILLS PROGRESSIVE: Start with basic editing (remove mistakes, normalize audio). Add music, transitions, and effects gradually.
- SHOW NOTES & SEO: Include tasks for writing show notes, episode descriptions, and keyword-optimized titles for every episode.
- DISTRIBUTION: Submit to ALL major platforms (Spotify, Apple Podcasts, Google Podcasts, Amazon Music, etc.) using a hosting service.
- CONSISTENT SCHEDULE: Pick a release schedule (weekly, biweekly) and NEVER miss it. Consistency builds audience trust.
- GUEST OUTREACH: Include tasks for researching, contacting, and scheduling guests. Start with accessible guests, build to bigger names.
- AUDIENCE GROWTH: Include tactics — cross-promotion with other podcasts, social media clips, newsletter, SEO, guest appearances on other shows.
- MONETIZATION: Plan monetization progressively — sponsorships (after ~1K downloads/episode), Patreon/membership, merchandise, live events.
- COMMUNITY BUILDING: Include tasks for building a listener community (Discord, social media group, newsletter, listener Q&A episodes).
- ANALYTICS TRACKING: Include monthly analytics review (downloads per episode, listener retention, growth trends, top episodes).
"""

    extra_calibration_hints = """
- Ask about the podcast concept and target audience
- Ask about current equipment (microphone, recording setup)
- Ask about solo vs co-host vs interview format preference
- Ask about technical skills (audio editing, recording experience)
- Ask about time available for production per week
- Ask about goals (fun project, thought leadership, monetization)
"""


class AppDevelopmentProcessor(BasePlanProcessor):
    """Building and launching a mobile or web application."""

    category = "app_dev"
    display_name = "Développement d’Application"

    domain_rules = """
- PROBLEM VALIDATION FIRST: Conduct 10+ user interviews before writing any code. Validate that the problem exists and people want a solution.
- WIREFRAME/PROTOTYPE BEFORE CODE: Create wireframes or a clickable prototype (Figma, Balsamiq) and test with potential users before development.
- MVP FEATURES ONLY: Ruthlessly cut features to the absolute minimum for launch. If it’s not core to solving the main problem, it’s post-launch.
- TECH STACK BY TEAM SKILLS: Choose tech stack based on team’s existing skills, not hype. Include a tech stack decision task with pros/cons analysis.
- CI/CD FROM DAY 1: Set up continuous integration and deployment pipeline before writing feature code. Include automated testing from the start.
- USER TESTING AT EVERY MILESTONE: Include user testing sessions at every major milestone (prototype, alpha, beta). Never build in isolation.
- ANALYTICS INTEGRATION: Include analytics setup (Mixpanel, Firebase, PostHog) early — track user behavior from first beta.
- APP STORE OPTIMIZATION (ASO): Include tasks for ASO research — keywords, screenshots, descriptions, and ratings strategy before launch.
- BETA TESTING PROGRAM: Include a structured beta program (TestFlight/Play Console beta) with feedback collection system.
- FEEDBACK LOOP: Include tasks for collecting, categorizing, and prioritizing user feedback. Build a feedback-to-feature pipeline.
- PERFORMANCE MONITORING: Include tasks for setting up error tracking (Sentry), performance monitoring, and crash reporting.
- SECURITY BASICS: Include security tasks (authentication, data encryption, OWASP top 10 review, privacy policy, GDPR compliance).
- MARKETING PRE-LAUNCH: Include pre-launch marketing tasks (landing page, email list, social media, Product Hunt preparation).
- LAUNCH DAY CHECKLIST: Include a detailed launch day checklist (store submission, monitoring, support readiness, announcement plan).
"""

    extra_calibration_hints = """
- Ask about the app idea and the problem it solves
- Ask about target users (who and how many potential users)
- Ask about current technical skills (beginner, intermediate, experienced developer)
- Ask about budget available for development tools and services
- Ask about team (solo developer or team)
- Ask about platform target (iOS, Android, web, cross-platform)
"""


class BookWritingProcessor(BasePlanProcessor):
    """Writing, editing, and publishing a book (fiction or non-fiction)."""

    category = "book"
    display_name = "Écrire & Publier un Livre"

    domain_rules = """
- OUTLINE/STRUCTURE FIRST: Spend 2 weeks minimum on outline, chapter structure, and character/argument development before writing prose.
- DAILY WORD COUNT TARGET: Set a realistic daily word count (500-2000 words depending on schedule). Track daily. Consistency is everything.
- FIRST DRAFT WITHOUT EDITING: Write the first draft straight through WITHOUT editing. Resist the urge to revise — get the story/content down first.
- DRAFT COMPLETION BEFORE REVISION: Complete the entire first draft before starting ANY revision. Never polish chapter 1 endlessly.
- BETA READERS: Include tasks to recruit 3-5 beta readers and create a structured feedback questionnaire for them.
- PROFESSIONAL EDITOR: Budget for a professional editor (developmental edit, copy edit, proofread). Include research and hiring tasks.
- COVER DESIGN: Include tasks for cover design research, hiring a designer, or learning cover design tools. Never DIY a cover without skills.
- ISBN/PUBLISHING SETUP: Include tasks for obtaining ISBN, setting up publishing accounts (KDP, IngramSpark, etc.), formatting for print and ebook.
- SELF-PUBLISH VS TRADITIONAL: Include a decision task — if traditional, include query letter writing, agent research, and submission tasks.
- LAUNCH STRATEGY: Include a book launch plan (launch date, pre-orders, ARC readers, launch team, social media campaign).
- MARKETING PLAN: Include ongoing marketing tasks — email list building, social media presence, book reviews, blog/podcast appearances.
- AUDIOBOOK CONSIDERATION: Include tasks to evaluate audiobook production (ACX, Findaway Voices) as additional revenue stream.
"""

    extra_calibration_hints = """
- Ask about the genre or type of book (fiction, non-fiction, memoir, guide)
- Ask about current progress (idea stage, outline, partial draft, complete draft)
- Ask about writing experience (first book or experienced author)
- Ask about publishing goal (self-publish, traditional, hybrid)
- Ask about time available for writing per day/week
- Ask about target audience and comparable books (comps)
"""


class OnlineCourseProcessor(BasePlanProcessor):
    """Creating, launching, and selling an online course or training program."""

    category = "online_course"
    display_name = "Créer un Cours en Ligne"

    domain_rules = """
- AUDIENCE RESEARCH FIRST: Conduct thorough audience research and validation — surveys, interviews, existing community engagement — before creating content.
- COURSE OUTLINE: Structure the course into modules and lessons. Include a detailed outline task with learning objectives per module.
- PILOT VERSION: Create a minimum viable course and test with at least 1 student before full production. Iterate based on feedback.
- RECORDING SETUP: Good audio quality is more important than video quality. Include tasks for microphone setup, acoustic treatment, and test recordings.
- PLATFORM SELECTION: Include a platform comparison task (Teachable, Udemy, Thinkific, own site) based on control, pricing, and audience access.
- PRICING RESEARCH: Include tasks for competitor pricing analysis and value-based pricing strategy. Test pricing with early buyers.
- LAUNCH STRATEGY: Build an email list pre-launch (minimum 100 subscribers). Include a launch sequence (teaser, early bird, open cart, close cart).
- STUDENT SUPPORT SYSTEM: Include tasks for setting up student support (community, Q&A, office hours, feedback channels).
- FEEDBACK ITERATION: Include tasks for collecting course reviews and improving content after each cohort or quarterly for evergreen courses.
- COMPLETION RATE OPTIMIZATION: Include tasks for improving completion rates — shorter lessons, progress tracking, certificates, community accountability.
- MARKETING FUNNEL: Include tasks for building a marketing funnel — free content (blog, YouTube, webinar) → email list → course sale.
- TESTIMONIALS COLLECTION: Include tasks for systematically collecting and featuring student testimonials and success stories.
"""

    extra_calibration_hints = """
- Ask about the course topic and their expertise level in it
- Ask about target audience (who would take this course)
- Ask about existing audience or email list
- Ask about technical skills (video editing, platform experience)
- Ask about time available for course creation
- Ask about revenue goals (side income, full-time business)
"""


class AcademicResearchProcessor(BasePlanProcessor):
    """Thesis, dissertation, academic research, PhD, scientific publications."""

    category = "research"
    display_name = "Recherche Académique"

    domain_rules = """
- LITERATURE REVIEW METHODOLOGY: Start with a structured literature review — define search terms, databases (Google Scholar, PubMed, Scopus), inclusion/exclusion criteria, and a reading schedule.
- RESEARCH QUESTION REFINEMENT: Dedicate early milestones to iteratively refining the research question. It should be specific, measurable, and feasible within the timeline.
- METHODOLOGY DESIGN: Include tasks for choosing and justifying the research methodology (qualitative, quantitative, mixed methods). Plan pilot studies if applicable.
- IRB/ETHICS APPROVAL TIMELINE: If human subjects are involved, include ethics committee/IRB submission as an early milestone — approval can take 4-12 weeks.
- DATA COLLECTION PLANNING: Include detailed data collection tasks — instruments, sample recruitment, consent forms, data storage protocols.
- STATISTICAL ANALYSIS PREPARATION: Include tasks for choosing statistical methods, learning necessary software (R, SPSS, Python), and planning the analysis pipeline BEFORE collecting data.
- WRITING SCHEDULE (SECTIONS NOT PAGES): Plan writing by sections (Introduction, Literature Review, Methodology, Results, Discussion, Conclusion) — not page counts. Each section gets its own milestone.
- PEER REVIEW PREPARATION: Include tasks for internal review cycles — advisor feedback, peer review exchanges, revision rounds. Budget 2-4 weeks per review cycle.
- CONFERENCE SUBMISSION DEADLINES: Map relevant conference deadlines and plan abstract/paper submissions as milestones.
- ADVISOR COMMUNICATION SCHEDULE: Include regular advisor meetings (biweekly minimum) and tasks to prepare progress reports for each meeting.
- CITATION MANAGEMENT: Include a task to set up and maintain a citation manager (Zotero, Mendeley) from day one. Organize references by theme.
- THESIS/DISSERTATION MILESTONES: Plan defense preparation (mock defense, slide preparation, committee scheduling) at least 6-8 weeks before the target date.
"""

    extra_calibration_hints = """
- Ask about the research field and specific topic area
- Ask about current stage (proposal, data collection, writing, revision)
- Ask about advisor relationship and meeting frequency
- Ask about deadline (defense date, submission deadline, conference date)
- Ask about methodology experience (qualitative, quantitative, mixed)
- Ask about access to data, labs, or research subjects
"""


class CompetitiveExamProcessor(BasePlanProcessor):
    """Competitive exams, civil service exams, entrance exams, bar exam."""

    category = "competitive_exam"
    display_name = "Concours & Examens Compétitifs"

    domain_rules = """
- SYLLABUS MAPPING (WEIGHT PER TOPIC): Start by mapping the full syllabus with the weight/coefficient of each topic. This determines time allocation.
- TIME ALLOCATION PROPORTIONAL TO TOPIC WEIGHT: Dedicate study time proportional to each topic's weight in the exam. High-coefficient topics get more hours.
- DAILY REVISION SCHEDULE: Include a structured daily schedule — morning for new material, afternoon for practice, evening for revision of the day's content.
- WEEKLY FULL-LENGTH MOCK TESTS FROM MIDPOINT: Schedule weekly timed mock tests starting from the halfway point of the preparation timeline. Analyze every result.
- ERROR ANALYSIS LOG: Include a task to maintain an error log — record every mistake, categorize by topic, and review the log weekly to target weak areas.
- TIME MANAGEMENT STRATEGY PER SECTION: Include tasks to practice time allocation per section of the exam. Develop a strategy for each section type (MCQ, essay, oral).
- CURRENT AFFAIRS IF APPLICABLE: For exams with general knowledge/current affairs components, include daily 30-min news review and weekly synthesis tasks.
- GROUP STUDY FOR DISCUSSION TOPICS: Include tasks to join or form a study group for oral preparation, debate practice, and knowledge exchange.
- PREVIOUS YEAR PAPERS ANALYSIS: Include a task to analyze the last 5-10 years of papers — identify recurring themes, question patterns, and difficulty trends.
- INTERVIEW PREPARATION IF APPLICABLE: For exams with an interview/oral stage, include mock interview sessions starting 4-6 weeks before the oral date.
- STRESS MANAGEMENT: Include regular stress management tasks — exercise, breathing techniques, sleep hygiene, and exam-day simulation to reduce anxiety.
"""

    extra_calibration_hints = """
- Ask about the specific exam name and date
- Ask about current preparation stage (just starting, mid-preparation, revision phase)
- Ask about previous attempts (first try or retaking)
- Ask about daily study time available
- Ask about strongest and weakest subjects in the syllabus
- Ask about access to preparation resources (books, courses, coaching)
"""


class DataScienceAIProcessor(BasePlanProcessor):
    """Data science, machine learning, deep learning, AI, data analysis."""

    category = "data_science"
    display_name = "Data Science & IA"

    domain_rules = """
- MATH FOUNDATIONS FIRST: Start with linear algebra, statistics, and calculus fundamentals. Without these, ML algorithms are black boxes. Dedicate first 15-20% of the plan to math.
- PYTHON/R PROFICIENCY: Include tasks for mastering Python (preferred) or R — focus on syntax, data structures, functions, and OOP basics before touching ML libraries.
- DATA MANIPULATION (PANDAS, NUMPY): Include structured exercises with pandas and numpy — data cleaning, transformation, merging, grouping. This is 80% of real data science work.
- VISUALIZATION: Include tasks for learning matplotlib, seaborn, and/or plotly. Every analysis should produce clear, interpretable visualizations.
- SQL: Include SQL proficiency tasks — most real-world data lives in databases. Practice complex queries, joins, window functions.
- MACHINE LEARNING THEORY THEN PRACTICE: For each ML algorithm, follow the pattern: theory → math behind it → implementation from scratch → scikit-learn usage → real dataset project.
- KAGGLE COMPETITIONS FOR PORTFOLIO: Include tasks to participate in Kaggle competitions progressively (start with Getting Started, move to Featured). Each competition is a portfolio piece.
- DEEP LEARNING AFTER ML BASICS: Do NOT start deep learning until classical ML is solid. Include DL tasks only after regression, classification, clustering, and ensemble methods are mastered.
- MLOPS BASICS: Include tasks for model deployment basics — Docker, APIs (Flask/FastAPI), cloud platforms, CI/CD for ML pipelines.
- DOMAIN EXPERTISE PAIRING: Include tasks to apply data science to a specific domain of interest (healthcare, finance, NLP, computer vision) for specialization.
- ETHICS IN AI: Include tasks on bias detection, fairness metrics, explainability (SHAP, LIME), and responsible AI practices.
- MODEL DEPLOYMENT: Include end-to-end project tasks — from data collection to deployed model — at least twice during the plan.
- PAPER READING HABIT: Include a weekly task to read and summarize one ML/AI research paper (arXiv, Papers With Code).
"""

    extra_calibration_hints = """
- Ask about current math and programming background
- Ask about specific goal (career transition, upskilling, research, personal projects)
- Ask about preferred learning format (courses, books, hands-on projects)
- Ask about target domain for data science application
- Ask about familiarity with Python, R, SQL, or other tools
- Ask about access to computing resources (local machine, cloud, GPU)
"""


class CybersecurityProcessor(BasePlanProcessor):
    """Cybersecurity, ethical hacking, penetration testing, infosec."""

    category = "cybersecurity"
    display_name = "Cybersécurité"

    domain_rules = """
- NETWORKING FUNDAMENTALS FIRST: Start with TCP/IP, DNS, HTTP, OSI model, subnetting. Without networking knowledge, security concepts will not stick.
- LINUX PROFICIENCY: Include tasks for mastering Linux command line — file system, permissions, processes, networking commands, bash scripting. Most security tools run on Linux.
- CTF PARTICIPATION PROGRESSIVE: Include Capture The Flag challenges with progressive difficulty — start with beginner platforms (PicoCTF, OverTheWire) and advance to HackTheBox, TryHackMe.
- CERTIFICATION PATH: Follow the standard path: CompTIA Security+ → CEH (Certified Ethical Hacker) → OSCP (Offensive Security). Include study + practice milestones for each.
- HOME LAB SETUP: Include a task to set up a home lab environment (VirtualBox/VMware, Kali Linux, vulnerable VMs like DVWA, Metasploitable, VulnHub machines).
- BUG BOUNTY PLATFORMS: Include tasks to join bug bounty platforms (HackerOne, Bugcrowd) after intermediate skills are built. Start with VDPs (Vulnerability Disclosure Programs).
- ETHICAL HACKING METHODOLOGY: Teach and practice the methodology: Reconnaissance → Scanning → Enumeration → Exploitation → Post-Exploitation → Reporting.
- REPORT WRITING: Include tasks for writing professional vulnerability reports — clear description, impact assessment, reproduction steps, remediation recommendations.
- CONTINUOUS LEARNING: Include weekly tasks for reading CVE disclosures, security blogs (Krebs, TheHackerNews), and attending virtual conferences (DEF CON talks, BSides).
- LEGAL BOUNDARIES UNDERSTANDING: Include tasks on computer crime laws, authorization scoping, and ethical guidelines. NEVER practice on unauthorized systems.
- TOOL PROFICIENCY: Include structured learning for key tools — Burp Suite, Nmap, Metasploit, Wireshark, John the Ripper, Hashcat, Gobuster, SQLmap.
- BLUE TEAM + RED TEAM BALANCE: Include both offensive (red team) and defensive (blue team) tasks — log analysis, SIEM, incident response alongside penetration testing.
"""

    extra_calibration_hints = """
- Ask about current IT/networking knowledge level
- Ask about specific cybersecurity interest (pentesting, forensics, SOC analyst, malware analysis)
- Ask about target certification or career goal
- Ask about available lab equipment and computing resources
- Ask about programming experience (Python, Bash, C)
- Ask about familiarity with Linux and networking concepts
"""


class TeachingMentoringProcessor(BasePlanProcessor):
    """Teaching, tutoring, mentoring, training, workshop facilitation."""

    category = "teaching"
    display_name = "Enseignement & Mentorat"

    domain_rules = """
- SUBJECT MATTER EXPERTISE VERIFICATION: Include self-assessment and knowledge gap tasks — you cannot teach what you do not deeply understand. Dedicate time to mastering content before teaching it.
- CURRICULUM DESIGN: Include tasks for designing a structured curriculum — learning objectives, progression, prerequisites, and alignment with standards or learner needs.
- LESSON PLANNING METHODOLOGY: Include tasks for creating detailed lesson plans — objectives, activities, timing, materials, assessment. Use backward design (start from desired outcomes).
- STUDENT ENGAGEMENT TECHNIQUES: Include tasks to learn and practice engagement strategies — questioning techniques, active learning, group work, gamification, real-world examples.
- ASSESSMENT DESIGN: Include tasks for creating formative (ongoing) and summative (final) assessments — rubrics, quizzes, projects, peer evaluation criteria.
- FEEDBACK DELIVERY: Include tasks on constructive feedback methods — specific, actionable, timely, balanced (strengths + areas for improvement). Practice the feedback sandwich.
- CLASSROOM MANAGEMENT: Include tasks for developing management strategies — rules, routines, transitions, handling disruptions, creating a safe learning environment.
- TECHNOLOGY INTEGRATION: Include tasks for learning and incorporating educational technology — LMS platforms, interactive tools (Kahoot, Miro, Mentimeter), video creation, online collaboration.
- DIFFERENTIATION FOR LEARNING STYLES: Include tasks for adapting content to different learners — visual, auditory, kinesthetic, reading/writing. Plan activities that address multiple styles.
- CONTINUOUS PROFESSIONAL DEVELOPMENT: Include tasks for ongoing growth — peer observation, workshops, reading pedagogy research, joining teaching communities.
- PEER OBSERVATION: Include tasks to observe experienced teachers/trainers and be observed for feedback. Schedule at least 2-3 observation cycles during the plan.
- STUDENT OUTCOME TRACKING: Include tasks for tracking learner progress — attendance, participation, assessment scores, qualitative feedback. Use data to adjust teaching strategies.
"""

    extra_calibration_hints = """
- Ask about the subject/topic they will be teaching
- Ask about the target audience (age group, level, professional context)
- Ask about teaching experience (first time, some experience, experienced)
- Ask about the teaching format (classroom, online, one-on-one, workshop)
- Ask about access to teaching tools and resources
- Ask about specific teaching challenges they want to overcome
"""




class AutomotiveProcessor(BasePlanProcessor):
    """Car repair, motorcycle maintenance, restoration, driving, tuning."""

    category = "automotive"
    display_name = "Automobile & Mécanique"

    domain_rules = """
- SAFETY FIRST: ALWAYS start with safety — jack stands for lifting, eye protection, gloves, well-ventilated workspace. NEVER work under a car supported only by a jack.
- REPAIR MANUAL: Before any repair task, include a task to obtain the vehicle-specific repair manual (Haynes, Chilton, or manufacturer FSM).
- TOOL CHECKLIST: Each repair job must include a specific tool checklist. Verify tool availability BEFORE starting any work.
- TORQUE SPECIFICATIONS: All fastener tasks must reference torque specs. Include a task to acquire a torque wrench if user doesn't have one.
- FLUID TYPES & AMOUNTS: Specify exact fluid types (oil weight, coolant type, brake fluid DOT rating) and quantities for every fluid-related task.
- DIAGNOSTIC BEFORE REPAIR: ALWAYS diagnose the problem before replacing parts. Include OBD2 scanner usage, visual inspection, and symptom documentation.
- PROGRESSIVE SKILL BUILDING: Start with basic maintenance (oil change, air filter, tire rotation) → intermediate (brakes, suspension) → advanced (engine, transmission). Never skip levels.
- PARTS SOURCING: Include tasks to research parts — OEM vs aftermarket vs remanufactured. Compare prices from multiple sources. Verify part numbers.
- ENVIRONMENTAL DISPOSAL: Include proper disposal tasks for used oil, coolant, brake fluid, batteries, and tires. Never pour fluids down drains.
- TEST DRIVE VERIFICATION: After ANY repair, include a structured test drive task — check for noises, leaks, warning lights, and proper operation at various speeds.
"""

    extra_calibration_hints = """
- Ask about the specific vehicle (make, model, year, mileage)
- Ask about current mechanical skill level (never worked on a car, basic maintenance, intermediate, advanced)
- Ask about available tools and workspace (garage, driveway, no space)
- Ask about the specific problem or project (maintenance, repair, restoration, modification)
- Ask about budget for parts and tools
- Ask about access to a repair manual or online resources for their vehicle
"""


class GamingEsportsProcessor(BasePlanProcessor):
    """Competitive gaming, esports, streaming, rank climbing, tournament preparation."""

    category = "gaming"
    display_name = "Gaming & Esports"

    domain_rules = """
- PRACTICE SCHEDULE WITH WARM-UP: Every practice session must start with 10-15 min warm-up (aim trainers, practice mode, mechanics drills) before ranked/competitive play.
- VOD REVIEW SESSIONS: Include weekly VOD review tasks — record gameplay and analyze mistakes, positioning, decision-making. Minimum 1 review per 5 hours of play.
- MECHANICAL SKILL DRILLS: Include daily mechanical practice (aim training, combo practice, build drills) separate from actual matches. 15-30 min focused drills.
- GAME KNOWLEDGE STUDY: Include tasks to study meta, patch notes, maps, matchups, and pro player strategies. Knowledge is as important as mechanics.
- TEAM COMMUNICATION: For team games, include tasks to practice callouts, develop team strategies, and review team performance together.
- MENTAL HEALTH BREAKS: MANDATORY breaks — 5 min every hour of play, stop after 2 consecutive losses (tilt prevention). Include non-gaming activities in the schedule.
- ERGONOMICS: Include setup optimization tasks — monitor height, chair posture, wrist position, eye strain prevention (20-20-20 rule), adequate lighting.
- RANK PROGRESSION MILESTONES: Set realistic rank milestones — typically 1 rank tier per 1-2 months of dedicated practice. Do NOT promise rapid rank climbing.
- TOURNAMENT PREPARATION: Include tasks for tournament registration, ruleset study, warm-up routines, and post-tournament analysis. Plan rest days before tournament.
- COACH/MENTOR FINDING: Recommend finding a coach or higher-ranked mentor for personalized feedback. Include tasks to research coaching options.
- STREAMING SETUP: If applicable, include progressive streaming tasks — setup (OBS, lighting, mic) → test streams → regular schedule. Do NOT let streaming distract from improvement.
"""

    extra_calibration_hints = """
- Ask about the specific game(s) they play and their current rank/level
- Ask about their goal (reach a specific rank, go pro, start streaming, win tournaments)
- Ask about available practice time per day/week
- Ask about their current setup (PC specs, peripherals, internet connection)
- Ask about whether they play solo or have a team
- Ask about physical health habits (exercise, sleep schedule, eye strain)
"""


class AdvancedCookingProcessor(BasePlanProcessor):
    """Gastronomy, pastry, bakery, fermentation, wine, professional cooking."""

    category = "culinary"
    display_name = "Cuisine Avancée & Gastronomie"

    domain_rules = """
- TECHNIQUE MASTERY BEFORE RECIPES: Master fundamental techniques (sautéing, braising, emulsions, reductions) before attempting complex recipes. Technique transfers across all cuisines.
- KNIFE SKILLS FOUNDATION: Include knife skills practice in the first milestone — proper grip, rocking motion, julienne, brunoise, chiffonade. This is non-negotiable for advanced cooking.
- MISE EN PLACE HABIT: Every cooking task must emphasize mise en place — all ingredients measured, prepped, and organized BEFORE cooking begins. Build this as an unbreakable habit.
- FLAVOR PROFILE UNDERSTANDING: Include tasks to study the 5 tastes (salt, sweet, acid, bitter, umami), flavor pairing principles, and seasoning techniques. Taste constantly while cooking.
- PLATING & PRESENTATION: Include progressive plating tasks — from clean basic plating to restaurant-style presentation. Photography of dishes for portfolio.
- FOOD SAFETY & HYGIENE: Include food safety certification or study — temperature danger zones, cross-contamination prevention, proper storage, allergen awareness.
- SEASONAL INGREDIENT SOURCING: Include tasks to visit local markets, build relationships with suppliers, understand seasonality, and select ingredients by quality (not just price).
- RECIPE DOCUMENTATION: Include tasks to document every recipe attempt — ingredients, process, timing, results, adjustments. Build a personal recipe book.
- CUISINE-SPECIFIC TECHNIQUES: For specific cuisines — French (mother sauces, stocks), Japanese (dashi, knife work, rice), Italian (pasta making, slow cooking) — include foundational tasks for that tradition.
- FERMENTATION TIMELINES: For fermentation projects, plan realistic timelines — sourdough starter (7-14 days), kimchi (3-7 days), miso (6-12 months). Include daily monitoring tasks.
- PASTRY PRECISION: For pastry/baking, ALWAYS use weights (grams), never volumes. Include tasks to acquire a precision scale. Temperature control is critical.
- WINE & PAIRING KNOWLEDGE: Include wine/beverage pairing study — basic regions, grape varieties, pairing principles. Tasting notes practice.
"""

    extra_calibration_hints = """
- Ask about current cooking skill level (home cook basics, intermediate, experienced home cook)
- Ask about specific culinary interest (French cuisine, pastry, fermentation, specific cuisine)
- Ask about their goal (personal enjoyment, dinner parties, professional career, food truck, restaurant)
- Ask about available kitchen equipment (oven type, stand mixer, specialized tools)
- Ask about dietary restrictions or preferences that may affect learning
- Ask about budget for ingredients and equipment
"""


class PhotographyVideoProcessor(BasePlanProcessor):
    """Photography, videography, filmmaking, editing, drone, content creation."""

    category = "photography"
    display_name = "Photo & Vidéo"

    domain_rules = """
- CAMERA FUNDAMENTALS: Start with the exposure triangle (aperture, shutter speed, ISO). Include tasks to practice each element in isolation before combining. Shoot in manual mode from week 2.
- COMPOSITION RULES THEN BREAK THEM: Teach rule of thirds, leading lines, framing, symmetry, negative space. After mastering them, include tasks to intentionally break rules for creative effect.
- SHOOTING ASSIGNMENTS: Include structured assignments — daily photo challenge (1 theme per day), weekly project (1 theme explored in depth). Consistent shooting is more important than gear.
- POST-PROCESSING WORKFLOW: Include progressive editing tasks — basic adjustments (exposure, white balance, crop) → color grading → advanced retouching. Establish a consistent editing workflow.
- BACKUP STRATEGY: Include tasks to set up a proper backup system — 3-2-1 rule (3 copies, 2 media types, 1 offsite). Losing photos is devastating. Plan storage early.
- PORTFOLIO CURATION: Include regular portfolio review tasks — select best 10-20 images per month, build a cohesive body of work. Quality over quantity.
- GENRE EXPLORATION: Include tasks to try different genres — portrait, landscape, street, macro, architecture, event. Explore before specializing.
- EQUIPMENT PROGRESSION: Do NOT buy everything at once. Start with what you have → learn its limits → upgrade strategically. Include tasks to research gear only when current equipment is genuinely limiting.
- CLIENT WORK PREPARATION: If targeting professional work, include tasks for pricing, contracts, model releases, client communication, and delivery workflows.
- PRINTING & EXHIBITION: Include tasks to print work, prepare for exhibitions or online galleries. Seeing physical prints changes your perspective on editing.
"""

    extra_calibration_hints = """
- Ask about current equipment (camera body, lenses, editing software)
- Ask about photography/video experience level (complete beginner, hobbyist, semi-pro)
- Ask about specific interest (portrait, landscape, wedding, documentary, YouTube, short film)
- Ask about their goal (personal hobby, freelance, full-time career, social media)
- Ask about available time for shooting and editing per week
- Ask about budget for equipment upgrades and software subscriptions
"""


class SpiritualityMindfulnessProcessor(BasePlanProcessor):
    """Meditation, yoga, mindfulness, wellness, spiritual growth, breathwork."""

    category = "spirituality"
    display_name = "Spiritualité & Bien-être"

    domain_rules = """
- PROGRESSIVE MEDITATION: Start at 2-5 minutes and increase by 1-2 minutes per week. Target 20 minutes by month 2-3. NEVER start with 30+ minute sessions — it causes frustration and dropout.
- JOURNALING DAILY: Include daily journaling tasks with specific prompts — morning intentions, evening reflections, gratitude lists, emotional processing. Not just "write in journal".
- GRATITUDE PRACTICE: Include a daily gratitude task — write 3 specific things you're grateful for. Specificity is key (not "my family" but "my sister called to check on me today").
- BREATHING EXERCISES: Include progressive breathwork — box breathing (4-4-4-4), diaphragmatic breathing, alternate nostril breathing. Start with 3-5 minutes, build to 10-15 minutes.
- BODY SCAN PROGRESSION: Include body scan meditation starting at 5 minutes, progressing to full 20-minute sessions. This builds interoception and relaxation skills.
- RETREAT PLANNING: If plan is longer than 3 months, include a task to research and plan a day retreat (month 2) and a weekend retreat (month 4+).
- READING SACRED/PHILOSOPHICAL TEXTS: Include progressive reading — start with accessible modern authors, then primary texts. 10-15 pages per day. Include reflection/discussion tasks.
- COMMUNITY/SANGHA FINDING: Include tasks to find a local or online meditation group, spiritual community, or practice partner. Regular group practice deepens individual practice.
- DIGITAL DETOX PERIODS: Include progressive digital detox — start with 1 hour screen-free daily, build to half-day weekly, then full-day monthly. Include specific activities for detox time.
- NATURE IMMERSION: Include weekly nature connection tasks — mindful walks, sitting meditation outdoors, forest bathing (shinrin-yoku). Minimum 30 minutes in nature per week.
- ETHICAL LIVING PRACTICES: Include tasks to explore and implement ethical practices — non-harming, truthfulness, generosity, simplicity. One practice focus per month.
- NON-JUDGMENTAL SELF-OBSERVATION: Emphasize in ALL tasks that the goal is observation without judgment. Include tasks to notice self-criticism patterns and practice self-compassion.
"""

    extra_calibration_hints = """
- Ask about current meditation or mindfulness experience (never tried, occasional, regular practice)
- Ask about specific spiritual tradition or interest (Buddhist, secular mindfulness, yoga, Christian contemplative, eclectic)
- Ask about their goal (stress reduction, spiritual growth, emotional healing, deeper self-knowledge)
- Ask about current daily routine and available time for practice
- Ask about physical health considerations (chronic pain, mobility issues that affect sitting meditation)
- Ask about any previous retreat or group practice experience
"""




class RelocationProcessor(BasePlanProcessor):
    """Moving to a new home, city, or country. Full relocation planning."""

    category = "relocation"
    display_name = "Déménagement"

    domain_rules = """
- TIMELINE WORKING BACKWARDS: Build the entire plan working backwards from the move date. Every task must have a deadline relative to D-day.
- DECLUTTER BEFORE PACKING: Include a full declutter phase BEFORE packing begins — room by room, sell/donate/discard decisions. Never pack what you don't need.
- ROOM-BY-ROOM PACKING SYSTEM: Organize packing by room with numbered boxes and an inventory spreadsheet. Label every box with room destination and contents summary.
- UTILITY TRANSFER SCHEDULE: Include a utility transfer timeline — electricity, gas, water, internet, phone. Schedule disconnection at old address and activation at new address with overlap.
- ADDRESS CHANGE CHECKLIST: Include a comprehensive address change checklist (30+ entities): bank, insurance, employer, tax office, Social Security, driver's license, vehicle registration, subscriptions, online accounts, postal redirection, doctors, dentists, schools, gym, loyalty programs, etc.
- MOVING COMPANY COMPARISON: Get minimum 3 quotes from moving companies. Include tasks for comparing prices, insurance coverage, availability, and reviews. Book 4-6 weeks in advance.
- INSURANCE VERIFICATION: Verify moving insurance coverage — both the moving company's liability and personal property insurance. Document high-value items with photos.
- ESSENTIAL BOX: Pack a "first night" essential box LAST (loaded first on truck): toiletries, change of clothes, medications, phone chargers, snacks, basic tools, important documents, bed sheets.
- CHILDREN AND PET PREPARATION: If applicable, prepare children and pets for the move — visit new neighborhood, maintain routines, arrange care on moving day.
- SCHOOL TRANSFER: If children are involved, research new schools, initiate transfer paperwork, and plan timing around school calendar.
- NEIGHBORHOOD RESEARCH: Research the new neighborhood thoroughly — shops, public transport, healthcare, safety, community groups, parks, restaurants.
- MEETING NEW NEIGHBORS: Include tasks for introducing yourself to new neighbors within the first 2 weeks. Join local community groups or associations.
- LOCAL SERVICES SETUP: Register with new local services — doctor, dentist, pharmacy, veterinarian, post office, town hall.
"""

    extra_calibration_hints = """
- Ask about the move date and whether it is flexible
- Ask about distance (local move, different city, different country)
- Ask about household size (solo, couple, family with children, pets)
- Ask about current living situation and new destination details
- Ask about budget available for the move
- Ask about whether they are renting or buying at the new location
"""


class WeddingPlanningProcessor(BasePlanProcessor):
    """Wedding planning, ceremony, reception, honeymoon."""

    category = "wedding"
    display_name = "Mariage"

    domain_rules = """
- BUDGET FIRST: Establish a realistic total budget BEFORE any other planning. Break it down by category (venue 40-50%, catering 25-30%, photo/video 10-15%, attire, flowers, music, decor, etc.).
- 12-MONTH MINIMUM TIMELINE: A well-planned wedding needs at least 12 months. If less time is available, prioritize ruthlessly and consider hiring a wedding planner.
- VENUE AND DATE BEFORE ANYTHING: Lock in the venue and date FIRST — everything else depends on these. Visit minimum 3 venues, check availability, and negotiate packages.
- VENDOR BOOKING PRIORITY ORDER: Book vendors in this order: (1) venue, (2) caterer/traiteur, (3) photographer/videographer, (4) officiant, (5) music/DJ, (6) florist, (7) decorator. Popular vendors book 12-18 months ahead.
- GUEST LIST MANAGEMENT: Finalize the guest list early — it determines venue size, catering cost, and invitation count. Use A-list/B-list strategy. Track RSVPs systematically.
- INVITATION TIMELINE: Save-the-dates 6-8 months before, formal invitations 6-8 weeks before, RSVP deadline 3 weeks before. Include all logistics (venue, parking, accommodations, dress code).
- MENU TASTING: Schedule menu tastings with caterers 4-6 months before. Account for dietary restrictions, allergies, and cultural preferences. Plan wine/beverage pairings.
- DRESS AND SUIT FITTING: Start dress shopping 8-10 months before (alterations take 2-3 months). Suit fittings 3-4 months before. Include shoes, accessories, and wedding party attire.
- CEREMONY PLANNING: Plan the ceremony structure — vows (personal or traditional), readings, music, processional/recessional, rituals. Include rehearsal scheduling.
- PHOTOGRAPHY AND VIDEOGRAPHY: Create a shot list, discuss style preferences, plan timeline for couple photos. Include tasks for engagement photoshoot if desired.
- MUSIC AND ENTERTAINMENT: Plan ceremony music, cocktail hour, reception music, first dance, special dances. Include playlist or DJ meeting with must-play/do-not-play lists.
- DECORATION AND THEME: Define color palette, theme, and decoration style. Include tasks for centerpieces, table settings, signage, lighting, and venue dressing.
- REHEARSAL: Schedule rehearsal dinner 1-2 days before. Include run-through of ceremony, coordination with wedding party, and logistics briefing.
- DAY-OF COORDINATOR: Strongly recommend hiring a day-of coordinator even on a budget. Include tasks for creating a detailed day-of timeline for all participants.
- HONEYMOON PLANNING: Start planning honeymoon 6+ months ahead. Include passport/visa checks, booking, packing, and post-wedding logistics (gift opening, thank-you cards).
- MARRIAGE LICENSE AND DOCUMENTS: Research legal requirements early — marriage license, banns publication (in France: mairie, 10 days minimum), required documents, witnesses.
"""

    extra_calibration_hints = """
- Ask about total budget available for the wedding
- Ask about approximate number of guests
- Ask about desired date or season
- Ask about style/theme preferences (formal, rustic, beach, intimate, destination)
- Ask about cultural or religious requirements for the ceremony
- Ask about whether they have a wedding planner or are planning themselves
"""


class CarPurchaseProcessor(BasePlanProcessor):
    """Buying a car — new or used, financing, insurance, registration."""

    category = "car_purchase"
    display_name = "Achat de Véhicule"

    domain_rules = """
- NEEDS ASSESSMENT FIRST: Start by assessing actual needs — city vs highway driving, number of passengers, cargo requirements, daily commute distance, parking constraints. Needs determine the vehicle type.
- TOTAL BUDGET CALCULATION: Calculate the TOTAL cost of ownership, not just the purchase price. Include insurance, maintenance, fuel/electricity, parking, tolls, registration, and depreciation. Plan for 15-20% above purchase price in annual running costs.
- NEW VS USED COMPARISON: Include tasks for objectively comparing new vs used options. Used cars save 20-40% but may have hidden issues. New cars have warranties but depreciate 20-30% in year one.
- FINANCING OPTIONS RESEARCH: Research all financing options — bank loan, dealer financing, leasing (LOA/LLD), personal savings. Compare APR, total cost, and monthly payments across minimum 3 lenders.
- TEST DRIVE CHECKLIST: Test drive minimum 3 different models. Include a checklist: comfort, visibility, noise level, acceleration, braking, parking ease, trunk space, tech features, passenger comfort.
- MECHANIC INSPECTION FOR USED CARS: For used vehicles, ALWAYS include a professional mechanic inspection before purchase. Check service history, accident history (Histovec in France), mileage verification, and MOT (contrôle technique) status.
- NEGOTIATION PREPARATION: Include tasks for researching fair market value (Argus, La Centrale, AutoScout24), preparing negotiation points, knowing dealer margins, and setting a walk-away price.
- TRADE-IN VALUE RESEARCH: If trading in a current vehicle, research its fair value independently before visiting dealers. Get minimum 3 valuations.
- INSURANCE QUOTES BEFORE PURCHASE: Get insurance quotes BEFORE finalizing the purchase — insurance cost varies significantly by model. Compare minimum 3 insurers. Consider all-risk vs third-party based on vehicle value.
- REGISTRATION AND TITLE TRANSFER: Include tasks for vehicle registration (carte grise), title transfer, and administrative paperwork. Budget processing time (1-3 weeks online, longer in person).
- MAINTENANCE SCHEDULE SETUP: After purchase, set up the maintenance schedule immediately — oil changes, tire rotation, brake inspection, filters. Register with a trusted mechanic or dealer service.
"""

    extra_calibration_hints = """
- Ask about primary use case (daily commute, family, leisure, professional)
- Ask about total budget including running costs
- Ask about preference for new or used
- Ask about fuel preference (gasoline, diesel, hybrid, electric)
- Ask about must-have features (safety, technology, comfort, performance)
- Ask about current vehicle situation (first car, replacement, additional)
"""


class LanguageImmersionProcessor(BasePlanProcessor):
    """Language immersion abroad — study abroad, exchange, au pair, working holiday."""

    category = "immersion"
    display_name = "Immersion Linguistique"

    domain_rules = """
- PRE-IMMERSION PREPARATION: Reach minimum A2 level in the target language BEFORE departure. Include intensive pre-departure study (3-6 months). Basics should not be learned abroad — use immersion time for real progress.
- HOUSING ARRANGEMENT: Research and secure housing well in advance — host family (best for immersion), shared apartment, student residence, or homestay. Include tasks for vetting options and signing contracts.
- SCHOOL OR COURSE ENROLLMENT: If attending a language school or university, complete enrollment, visa paperwork, and course selection 3-6 months before departure. Research accredited institutions.
- DAILY ROUTINE IN TARGET LANGUAGE: Plan a daily routine that maximizes target language exposure — morning news in TL, shopping in TL, journaling in TL, socializing in TL. Minimize native language use.
- LOCAL COMMUNITY INTEGRATION: Include tasks for joining local clubs, sports teams, volunteer groups, or hobby classes. Integration happens through shared activities, not just language exchanges.
- MEDIA CONSUMPTION PLAN: Create a structured media plan — local TV shows, podcasts, music, newspapers, social media in the target language. Progressive difficulty from subtitled to native content.
- LANGUAGE EXCHANGE PARTNER: Find a language exchange partner (tandem) within the first 2 weeks. Use apps like Tandem, HelloTalk, or local university boards. Schedule regular meetups.
- CULTURAL ACTIVITIES: Include cultural immersion tasks — visit museums, attend local festivals, try regional cuisine, explore historical sites, understand local customs and humor.
- TRAVEL WITHIN REGION: Plan weekend trips within the region/country to experience different accents, dialects, and cultures. Travel is part of the learning experience.
- DOCUMENTATION OF PROGRESS: Keep a language journal — record new expressions daily, track comfort level in different situations, do monthly self-assessments against CEFR descriptors.
- HOMESICKNESS MANAGEMENT: Include tasks for managing homesickness — regular but limited contact with home, building a local support network, maintaining a positive mindset journal, seeking help if needed.
- PRACTICAL TASKS IN TARGET LANGUAGE: Force all practical tasks in the target language — opening a bank account, seeing a doctor, dealing with administration, grocery shopping, asking for directions.
- RE-ENTRY PLANNING: Plan for return — how to maintain the language after immersion (online tutors, media, community groups, return trips). Language loss is real without maintenance.
"""

    extra_calibration_hints = """
- Ask about target language and current level (CEFR or self-assessment)
- Ask about destination country/city preferences
- Ask about duration of the immersion (weeks, months, year)
- Ask about the format (language school, university exchange, au pair, working holiday, independent)
- Ask about budget and funding sources (savings, scholarships, family support)
- Ask about previous travel or living abroad experience
"""


class DigitalNomadProcessor(BasePlanProcessor):
    """Digital nomad lifestyle — remote work while traveling, location independence."""

    category = "digital_nomad"
    display_name = "Nomade Digital"

    domain_rules = """
- REMOTE INCOME ESTABLISHED BEFORE DEPARTURE: Do NOT leave without a stable remote income source. Include tasks for securing remote work, building a freelance client base, or setting up an online business BEFORE traveling. Test remote work for 1-3 months at home first.
- CONNECTIVITY RESEARCH PER DESTINATION: Research internet quality and reliability for each destination. Include tasks for checking coworking spaces, cafe wifi, mobile data plans, and backup connectivity options (portable hotspot).
- COWORKING SPACES: Research and budget for coworking spaces in each destination. Include tasks for finding communities (Coworker, Nomad List, local Facebook groups). Coworking provides productivity, networking, and routine.
- TIME ZONE MANAGEMENT: Plan destinations around client/team time zones. Include tasks for establishing communication windows, async work practices, and tools (Slack, Notion, Loom). Avoid destinations with more than 6-hour difference from key clients.
- TRAVEL INSURANCE LONG-TERM: Get proper long-term travel insurance (SafetyWing, World Nomads, Genki) that covers medical, gear theft, and trip interruption. Standard travel insurance does NOT cover nomad lifestyles.
- TAX RESIDENCY PLANNING: Include tasks for understanding tax obligations — tax residency rules, declaring foreign income, digital nomad visa options, and consulting a tax professional specializing in expat/nomad taxation.
- MINIMAL GEAR SETUP: Plan a minimal but reliable gear setup — laptop, backup charger, universal adapter, noise-canceling headphones, portable monitor (optional). Include tasks for testing everything before departure and backup plans for gear failure.
- SLOW TRAVEL: Plan for minimum 1 month per destination. Rapid movement kills productivity and increases costs. Include tasks for finding monthly rentals (Airbnb monthly discount, local platforms, Facebook groups).
- COMMUNITY AND NETWORKING: Include tasks for connecting with nomad communities — Nomad List, local meetups, coworking events, online communities (Reddit, Facebook groups). Combat isolation with intentional socializing.
- HEALTH INSURANCE INTERNATIONAL: Research and secure international health insurance. Include tasks for finding English-speaking doctors, understanding local healthcare systems, and carrying essential medications.
- BANKING AND FINANCES: Set up multi-currency banking (Wise, Revolut, N26) before departure. Include tasks for notifying banks of travel, setting up international transfers, and budgeting per destination (cost of living varies dramatically).
- VISA MANAGEMENT: Research visa requirements for each destination. Include tasks for tracking visa durations, renewal requirements, and digital nomad visa options (Portugal, Estonia, Croatia, Thailand, etc.).
- ROUTINE MAINTENANCE WHILE TRAVELING: Establish and maintain a daily routine despite changing locations — fixed work hours, exercise, social time, exploration time. Include tasks for adapting the routine to each new destination.
"""

    extra_calibration_hints = """
- Ask about current income source and whether it is fully remote
- Ask about target destinations or regions of interest
- Ask about planned duration (trial period, 6 months, indefinite)
- Ask about budget per month for living expenses
- Ask about work schedule constraints (client meetings, time zones, deadlines)
- Ask about previous travel or remote work experience
"""


class DrivingLicenseProcessor(BasePlanProcessor):
    """Driving license preparation, highway code, driving lessons."""

    category = "driving"
    display_name = "Permis de Conduire"

    domain_rules = """
- THEORY EXAM FIRST: Prioritize highway code study and theory exam preparation before intensive practical lessons.
- OFFICIAL ENROLLMENT: Include task for enrolling in an official, certified driving school. Research reviews and pass rates.
- PRACTICE TEST SCHEDULE: Include regular online practice tests (Code de la route platforms) — daily 20-30 min sessions minimum.
- HIGHWAY CODE STUDY PLAN: Structure code study by theme (priority rules, signage, safety, eco-driving) with weekly chapter targets.
- LESSON BOOKING STRATEGY: Optimal driving lesson frequency is 2-3 per week. Fewer = skill regression between lessons. More = fatigue and diminishing returns.
- PARKING SPECIFIC PRACTICE: Dedicate at least 3-4 lessons specifically to parking (créneau, bataille, épi). Practice in varied environments.
- HIGHWAY DRIVING EXPOSURE: Include at minimum 2-3 highway driving sessions before the exam. Highway entry/exit and lane changes are exam-critical.
- NIGHT DRIVING PRACTICE: Include at least 1-2 night driving sessions. Night visibility, glare management, and adapted speed are tested.
- EXAM DAY PREPARATION: Include tasks for document verification (ID, convocation), adequate rest the night before, and route familiarity for the exam center.
- FAILURE RECOVERY PLAN: Include a contingency plan if theory or practical exam is failed — analyze weak points, schedule extra lessons, rebook exam without delay.
- POST-LICENSE CONFIDENCE BUILDING: Include tasks for solo driving practice after passing — varied routes, different weather conditions, parking practice.
- DEFENSIVE DRIVING HABITS: Include tasks for developing defensive driving habits — anticipation, safe following distance, mirror checks, blind spot awareness.
"""

    extra_calibration_hints = """
- Ask about previous driving experience (complete beginner, some experience, foreign license)
- Ask about whether theory exam (code) is already passed
- Ask about preferred driving school or if they need help choosing one
- Ask about available budget for lessons and exam fees
- Ask about time available per week for lessons and study
- Ask about any driving-related anxiety or specific fears
"""


class ExtremeSportsProcessor(BasePlanProcessor):
    """Skydiving, bungee jumping, paragliding, base jumping, extreme climbing."""

    category = "extreme_sports"
    display_name = "Sports Extrêmes"

    domain_rules = """
- ALWAYS PROFESSIONAL INSTRUCTION: For EVERY first attempt at any extreme sport, MANDATORY professional instruction from a certified instructor. NEVER plan solo first attempts.
- CERTIFIED EQUIPMENT ONLY: Include tasks for acquiring or renting certified, inspected equipment. No second-hand gear without professional inspection.
- PROGRESSIVE SKILL BUILDING: Follow a strict progression — indoor/simulated → controlled outdoor environment → open/real conditions. Never skip stages.
- SAFETY BRIEFING EVERY SESSION: Every practice session task must include a safety briefing component. Complacency kills in extreme sports.
- BUDDY SYSTEM: NEVER plan solo extreme sport sessions. Always include a partner, spotter, or group. Include tasks for finding reliable training partners.
- PHYSICAL CONDITIONING PREREQUISITES: Include prerequisite fitness tasks — core strength, flexibility, cardio endurance, grip strength as applicable to the sport.
- WEATHER ASSESSMENT SKILLS: Include tasks for learning to read weather conditions relevant to the sport (wind, thermals, visibility, precipitation, temperature).
- EMERGENCY PROTOCOLS: Include tasks for learning emergency procedures, first aid certification, and having emergency gear accessible.
- INSURANCE VERIFICATION: Include a task to verify insurance coverage for the specific extreme sport. Many standard policies exclude extreme sports.
- EQUIPMENT MAINTENANCE SCHEDULE: Include regular equipment inspection, maintenance, and replacement schedule tasks. Document equipment age and usage hours.
- MENTAL PREPARATION: Include tasks for fear management techniques — visualization, breathing exercises, progressive exposure, and knowing when to abort safely.
- COMMUNITY/CLUB ACCOUNTABILITY: Include tasks for joining a local club or community for the sport — accountability, shared knowledge, group safety, and motivation.
"""

    extra_calibration_hints = """
- Ask about the specific extreme sport they want to pursue
- Ask about current physical fitness level and any health conditions
- Ask about previous experience with any adventure or extreme sports
- Ask about access to facilities, clubs, or schools for the sport in their area
- Ask about budget for equipment, lessons, and certifications
- Ask about their comfort level with risk and fear management
"""


class RetirementHobbyProcessor(BasePlanProcessor):
    """Leisure activities for retirees, senior hobbies, post-retirement engagement."""

    category = "retirement_hobby"
    display_name = "Loisirs à la Retraite"

    domain_rules = """
- EXPLORATION PHASE: Start with an exploration phase — try 3-5 different activities before committing to one or two. Include taster sessions and trial periods.
- SOCIAL COMPONENT IMPORTANT: Prioritize activities with a social dimension — clubs, groups, classes. Combating isolation is as important as the activity itself.
- PHYSICAL ACTIVITY BALANCE: Include at least one gentle physical activity (walking, swimming, tai chi, yoga) alongside other hobbies for health maintenance.
- COGNITIVE STIMULATION: Include activities that challenge the brain — puzzles, learning new skills, strategy games, language learning, creative writing.
- BUDGET-FRIENDLY OPTIONS: Emphasize free or low-cost options first — community centers, libraries, free workshops, nature activities, online resources.
- TIME STRUCTURE: Help build a weekly routine with scheduled activities. Routine helps the transition from structured work life to retirement.
- TEACHING/SHARING SKILLS: Include tasks for sharing expertise — tutoring, mentoring, teaching workshops. Retirees have valuable knowledge to pass on.
- LEGACY PROJECTS: Include tasks for legacy activities — writing memoirs, recording family history, creating photo albums, documenting recipes or traditions.
- TRAVEL INTEGRATION: Include tasks for combining hobbies with travel — painting retreats, photography trips, cultural tours, walking holidays.
- VOLUNTEERING OPPORTUNITIES: Include volunteer activities that align with hobbies — garden volunteer at parks, reading to children, community kitchen, museum guide.
- TECHNOLOGY LEARNING: Include progressive technology learning tasks — smartphone, tablet, video calls, social media, online communities for the hobby.
- GRANDPARENT ACTIVITIES: Include inter-generational activity ideas — crafts with grandchildren, cooking together, storytelling, nature walks, teaching skills.
"""

    extra_calibration_hints = """
- Ask about when they retired or plan to retire
- Ask about hobbies or interests they've always wanted to explore
- Ask about physical abilities and any health limitations
- Ask about social preferences (group activities vs solo pursuits)
- Ask about budget available for hobbies and activities
- Ask about access to community centers, clubs, or groups nearby
"""


class CompetitionPrepProcessor(BasePlanProcessor):
    """Competition preparation, championships, contests, performance optimization."""

    category = "competition"
    display_name = "Préparation Compétition"

    domain_rules = """
- REGISTRATION AND DEADLINE AS ANCHOR: The competition date is the immovable anchor. ALL planning works backward from this date. Include registration task as milestone 1.
- PERIODIZATION: Structure training in phases — Base (aerobic/foundation) → Build (intensity increase) → Peak (competition-specific) → Taper (volume reduction 1-2 weeks before).
- SPECIFIC EVENT SIMULATION: Include at least 3-4 full event simulations under competition-like conditions (timing, rules, environment, pressure).
- MENTAL PERFORMANCE TRAINING: Include mental training tasks — visualization, pre-competition routines, stress management, focus techniques, positive self-talk.
- NUTRITION PERIODIZATION: Adapt nutrition to training phase — higher carbs during build phase, strategic fueling for peak, pre-competition meal planning.
- EQUIPMENT FINALIZATION: All equipment must be finalized and tested at least 2 weeks before competition. NEVER use new equipment on competition day.
- TRAVEL LOGISTICS: If competition requires travel, include tasks for booking, route planning, accommodation, and arriving 1-2 days early for acclimatization.
- RECOVERY PROTOCOL POST-COMPETITION: Include post-competition recovery tasks — active recovery, debrief, physical assessment, rest period before next training cycle.
- VIDEO/PERFORMANCE REVIEW: Include tasks for recording practice sessions and reviewing performance — technique analysis, identifying weaknesses, tracking improvements.
- COACH/EXPERT CONSULTATION: Include tasks for consulting with a coach, trainer, or expert specific to the competition discipline at key milestones.
- COMPETITOR ANALYSIS: Include tasks for researching competitors, understanding scoring criteria, and identifying competitive advantages and gaps.
- CONTINGENCY PLANS: Include backup plans for injury, illness, equipment failure, weather changes, or travel disruptions.
- CELEBRATION MILESTONE: Include a celebration task after the competition regardless of result — acknowledge the effort and commitment.
"""

    extra_calibration_hints = """
- Ask about the specific competition (sport, discipline, level, date)
- Ask about current performance level relative to competition standards
- Ask about training history and current training volume
- Ask about access to coaching, facilities, and training partners
- Ask about previous competition experience and results
- Ask about any injuries, limitations, or health concerns
"""


class LifeTransitionProcessor(BasePlanProcessor):
    """Divorce, grief, career change, starting over, major life changes."""

    category = "life_transition"
    display_name = "Transition de Vie"

    domain_rules = """
- ACKNOWLEDGE GRIEF/LOSS STAGE: Recognize that major life transitions involve grief — even positive changes. Include tasks for processing emotions without rushing.
- SUPPORT SYSTEM ACTIVATION: Include tasks for identifying and reaching out to supportive people — friends, family, support groups, community resources.
- PROFESSIONAL COUNSELING RECOMMENDED: ALWAYS recommend professional support (therapist, counselor, psychologist) as a first-milestone task. This plan supplements but does NOT replace professional care.
- FINANCIAL REASSESSMENT: Include a complete financial reassessment task — new budget, updated expenses, emergency fund review, income changes, legal financial obligations.
- ROUTINE REBUILDING: Include tasks for establishing new daily routines — sleep schedule, meals, exercise, social time. Structure provides stability during chaos.
- IDENTITY EXPLORATION: Include tasks for exploring who they are outside the previous situation — values reassessment, new interests, personal goals redefinition.
- GOAL REASSESSMENT: Include tasks for reviewing and updating all life goals — what still matters, what has changed, what new goals emerge from the transition.
- SELF-CARE NON-NEGOTIABLE: Include daily self-care tasks — exercise, proper nutrition, sleep hygiene, relaxation. Physical health supports emotional resilience.
- ONE MAJOR CHANGE AT A TIME: Do NOT plan multiple simultaneous major changes. Stabilize one area before addressing the next. Sequence changes thoughtfully.
- DOCUMENTATION FOR LEGAL/ADMIN: Include tasks for all administrative and legal documentation — address changes, account updates, insurance modifications, legal filings.
- SOCIAL CIRCLE EVOLUTION: Include tasks for evaluating and evolving social connections — who supports growth, who to distance from, new communities to join.
- NEW SKILLS/INTERESTS EXPLORATION: Include tasks for trying new activities, classes, or hobbies that represent the new chapter. Novelty aids identity rebuilding.
- PATIENCE WITH PROCESS: Set realistic timelines — major transitions take 1-2 years to fully process. Build in flexibility and self-compassion milestones.
- CELEBRATE SMALL PROGRESS: Include regular milestone celebrations for small wins — first week in new routine, first social outing, first month of stability.
"""

    extra_calibration_hints = """
- Ask about the specific transition they are going through (with sensitivity)
- Ask about their current support system (family, friends, professionals)
- Ask about the most urgent practical concern right now (housing, finances, legal, emotional)
- Ask about whether they are currently seeing a therapist or counselor
- Ask about children or dependents affected by the transition
- Ask about their timeline and any external deadlines (legal, financial, housing)
"""



class DatingProcessor(BasePlanProcessor):
    """Dating, seduction, finding love, relationship building."""

    category = "dating"
    display_name = "Rencontres & Séduction"

    domain_rules = """
- SELF-IMPROVEMENT ALONGSIDE DATING: Personal growth is the foundation — work on yourself (fitness, hobbies, career) simultaneously with dating efforts.
- PROFILE OPTIMIZATION: Include tasks for optimizing dating profiles — quality photos (varied, natural, recent), authentic bio writing, profile review by trusted friends.
- CONVERSATION STARTERS PRACTICE: Include exercises for opening conversations — practice openers, storytelling, humor, and asking engaging questions.
- DATE PLANNING VARIETY: Plan diverse date ideas (coffee, activity-based, cultural, outdoor) that encourage genuine connection over performance.
- REJECTION RESILIENCE BUILDING: Include progressive desensitization tasks — handle rejection as data, not failure. Journal rejections and lessons learned.
- RED FLAG AWARENESS: Include tasks for learning to identify red flags (love-bombing, boundary violations, inconsistency) and green flags.
- COMMUNICATION SKILLS: Include active listening practice, vulnerability exercises, expressing needs clearly, and understanding attachment styles.
- PACE RESPECT: Plan gradual relationship building — don't rush exclusivity or major decisions. Include check-in tasks to assess compatibility.
- SAFETY PROTOCOLS: ALWAYS include safety tasks — meet in public places, tell a friend your plans, trust your instincts, have an exit strategy.
- DIGITAL ETIQUETTE: Include guidelines for messaging frequency, response timing, transitioning from app to in-person, and managing multiple conversations.
- PERSONAL BOUNDARIES DEFINITION: Include tasks for defining and communicating personal boundaries (physical, emotional, time, digital).
- GENUINE INTEREST OVER TECHNIQUES: Focus on authentic connection — curiosity about the other person, shared values discovery, not pickup techniques or manipulation.
"""

    extra_calibration_hints = """
- Ask about what kind of relationship they are looking for (casual, serious, long-term)
- Ask about previous relationship experience and what they learned
- Ask about their current social life and where they meet people
- Ask about specific challenges they face in dating (approach anxiety, conversation, commitment)
- Ask about their values and deal-breakers in a partner
- Ask about their comfort level with dating apps vs in-person approaches
"""


class ConfidenceProcessor(BasePlanProcessor):
    """Self-confidence, self-esteem, assertiveness, overcoming shyness."""

    category = "confidence"
    display_name = "Confiance en Soi"

    domain_rules = """
- SMALL WINS DAILY: Build confidence through progressive exposure — start with micro-challenges and increase difficulty gradually each week.
- POSITIVE SELF-TALK PRACTICE: Include daily positive affirmation and cognitive reframing exercises. Replace self-criticism with self-encouragement.
- BODY LANGUAGE EXERCISES: Include posture exercises (power poses, eye contact practice, firm handshake, open stance) as daily 5-minute tasks.
- COMFORT ZONE EXPANSION: Plan graduated challenges — each week slightly outside the comfort zone. Track discomfort level to see progress over time.
- JOURNALING PROGRESS: Include daily confidence journaling — wins of the day, moments of courage, evidence against negative beliefs.
- SOCIAL EXPERIMENTS: Progress from low-risk (smile at stranger, ask for directions) to high-risk (public speaking, leading a meeting, cold approaching).
- SKILL BUILDING: Competence breeds confidence — include tasks for developing specific skills that matter to the user. Mastery reduces imposter syndrome.
- BOUNDARY SETTING PRACTICE: Include graduated boundary exercises — saying no to small requests, expressing preferences, then tackling harder boundaries.
- COMPARISON DETOX: Include social media usage reduction tasks and exercises to focus on personal progress rather than comparing to others.
- SELF-COMPASSION EXERCISES: Include Kristin Neff-style self-compassion practices — self-kindness, common humanity, mindfulness of emotions.
- ACHIEVEMENT DOCUMENTATION: Maintain a running "evidence file" of accomplishments, compliments received, and challenges overcome.
- VISUALIZATION PRACTICE: Include daily visualization of confident behavior in upcoming situations — mental rehearsal before real events.
- PROFESSIONAL SUPPORT IF DEEP-ROOTED: For trauma-based low confidence, social anxiety disorder, or severe imposter syndrome, FIRST task is consulting a therapist/psychologist.
"""

    extra_calibration_hints = """
- Ask about specific situations where they lack confidence (social, professional, romantic, public)
- Ask about the origin of their confidence issues (childhood, specific event, gradual)
- Ask about their current coping mechanisms
- Ask about areas where they DO feel confident (leverage existing strengths)
- Ask about social support system and relationships
- Ask about whether they have considered or are seeing a therapist
"""


class LeadershipProcessor(BasePlanProcessor):
    """Leadership skills, team management, executive presence, decision-making."""

    category = "leadership"
    display_name = "Leadership & Management"

    domain_rules = """
- SELF-AWARENESS ASSESSMENT FIRST: Start with leadership style assessments (DISC, MBTI, 360 feedback) to understand current strengths and blind spots.
- COMMUNICATION SKILLS FOUNDATION: Include tasks for developing clear, concise communication — active listening, giving instructions, sharing vision, storytelling.
- DELEGATION PRACTICE: Include graduated delegation exercises — start small, define expectations clearly, resist micromanaging, debrief results.
- FEEDBACK GIVING AND RECEIVING: Include practice with feedback frameworks (SBI, COIN) — both giving constructive feedback and receiving criticism gracefully.
- TEAM MOTIVATION STRATEGIES: Include tasks for learning motivational approaches — recognition, autonomy, purpose alignment, individual growth paths.
- CONFLICT RESOLUTION: Include conflict management frameworks (Thomas-Kilmann model) and practice scenarios for mediating disagreements.
- DECISION-MAKING FRAMEWORKS: Include tasks for learning structured decision-making — RAPID, pros/cons analysis, decision journals, reversible vs irreversible decisions.
- STRATEGIC THINKING EXERCISES: Include tasks for developing strategic vision — scenario planning, competitive analysis, long-term goal setting, OKR frameworks.
- MENTORING OTHERS: Include tasks for developing mentoring skills — active sponsorship, knowledge sharing, creating growth opportunities for team members.
- PUBLIC SPEAKING PROGRESSION: Progress from team meetings to department presentations to company-wide talks to external conferences.
- EXECUTIVE PRESENCE: Include exercises for gravitas (calm under pressure, decisive communication), communication polish, and professional appearance.
- EMOTIONAL INTELLIGENCE DEVELOPMENT: Include tasks for self-regulation, empathy exercises, social awareness, and relationship management.
- NETWORKING WITH LEADERS: Include tasks for connecting with other leaders — peer groups, executive coaching, leadership communities, conferences.
- READING LEADERSHIP LITERATURE: Include a reading list with one leadership book per month (classics + modern) with application tasks after each.
- LEADING BY EXAMPLE METRICS: Track specific leadership behaviors weekly — consistency, transparency, follow-through on commitments.
"""

    extra_calibration_hints = """
- Ask about current role and team size (or aspiration if not yet a leader)
- Ask about specific leadership challenges they face
- Ask about leadership style they admire and want to develop
- Ask about organizational context (startup, corporate, non-profit, community)
- Ask about previous leadership experience (formal or informal)
- Ask about relationship with their own manager or mentors
"""


class NetworkingProcessor(BasePlanProcessor):
    """Professional networking, building connections, mentorship, community."""

    category = "networking"
    display_name = "Réseautage Professionnel"

    domain_rules = """
- TARGET LIST: Include tasks for creating a strategic list of people to connect with — industry leaders, potential mentors, peers, complementary professionals.
- VALUE-FIRST APPROACH: Always give before asking — include tasks for providing value (share articles, make introductions, offer expertise, congratulate achievements).
- LINKEDIN OPTIMIZATION: Include tasks for optimizing LinkedIn profile — professional photo, compelling headline, detailed experience, regular content posting.
- EVENT ATTENDANCE SCHEDULE: Plan monthly networking events — industry conferences, meetups, professional associations, alumni gatherings, workshops.
- FOLLOW-UP SYSTEM: Include the 48-hour rule — follow up within 48h after every meeting. Create a CRM-like system for tracking contacts and interactions.
- ELEVATOR PITCH PREPARATION: Include tasks for crafting and practicing a 30-second, 1-minute, and 3-minute pitch for different contexts.
- INFORMATIONAL INTERVIEW REQUESTS: Include tasks for requesting and conducting informational interviews — research the person, prepare questions, respect their time.
- COMMUNITY CONTRIBUTION: Include tasks for giving back — volunteer to speak at events, write articles, mentor juniors, contribute to industry groups.
- RELATIONSHIP NURTURING: Schedule monthly touchpoints with key contacts — birthday messages, congratulations, sharing relevant content, coffee catch-ups.
- REFERRAL SYSTEM: Include tasks for building a referral system — be generous with referrals, make it easy for others to refer you, track referral outcomes.
- ONLINE + OFFLINE BALANCE: Plan a mix of digital networking (LinkedIn, Twitter, communities) and in-person events for different relationship depths.
- INDUSTRY-SPECIFIC PLATFORMS: Include tasks for identifying and engaging on platforms specific to their industry (GitHub for tech, Behance for design, etc.).
"""

    extra_calibration_hints = """
- Ask about current network size and quality (how many meaningful professional contacts)
- Ask about specific networking goals (job search, business development, industry change, mentorship)
- Ask about comfort level with networking (natural networker vs finds it awkward)
- Ask about industry and professional context
- Ask about time available for networking activities per week
- Ask about existing presence on LinkedIn and other professional platforms
"""


class CommunicationProcessor(BasePlanProcessor):
    """Communication skills, self-expression, persuasion, public speaking, listening."""

    category = "communication"
    display_name = "Communication & Expression"

    domain_rules = """
- ACTIVE LISTENING EXERCISES DAILY: Include daily active listening practice — paraphrasing, asking clarifying questions, withholding judgment, summarizing conversations.
- NON-VIOLENT COMMUNICATION PRACTICE: Include NVC (Marshall Rosenberg) exercises — observations vs judgments, feelings, needs, requests. Practice weekly.
- STORYTELLING SKILLS: Include storytelling structure practice (STAR method, hero's journey, three-act structure) for both professional and personal contexts.
- BODY LANGUAGE AWARENESS: Include exercises for reading others' body language and improving own — eye contact, gestures, posture, mirroring, facial expressions.
- WRITTEN COMMUNICATION IMPROVEMENT: Include tasks for improving email writing, report structure, social media presence, and clarity in written messages.
- DIFFICULT CONVERSATIONS FRAMEWORK: Include practice with difficult conversation models — preparation, opening, exploring perspectives, finding solutions, closing.
- FEEDBACK MODELS: Include practice with SBI (Situation-Behavior-Impact) and COIN (Connection-Observation-Impact-Next steps) frameworks for giving and receiving feedback.
- CROSS-CULTURAL COMMUNICATION: Include awareness tasks for cultural communication differences — high-context vs low-context, directness, formality, non-verbal norms.
- PRESENTATION SKILLS PROGRESSION: Progress from 1-minute pitches to 5-minute talks to 15-minute presentations to full keynotes. Include slide design and audience engagement.
- EMOTIONAL REGULATION DURING CONFLICT: Include techniques for staying calm — breathing exercises, pause before responding, emotional labeling, de-escalation phrases.
- EMPATHY EXERCISES: Include perspective-taking tasks — practice seeing situations from others' viewpoints, ask about feelings, validate emotions before problem-solving.
- VOCAL VARIETY PRACTICE: Include exercises for improving vocal delivery — pace variation, volume control, pausing for effect, tone modulation, eliminating filler words.
- INTERVIEW SKILLS: Include mock interview practice — behavioral questions (STAR method), salary negotiation, asking insightful questions, confident self-presentation.
"""

    extra_calibration_hints = """
- Ask about specific communication challenges (public speaking, conflict, written, cross-cultural)
- Ask about professional context (meetings, presentations, client interactions, team communication)
- Ask about personal communication goals (relationships, assertiveness, persuasion)
- Ask about current strengths and weaknesses in communication
- Ask about any speech-related concerns (accent, stutter, anxiety)
- Ask about languages they communicate in professionally
"""



class StartupProcessor(BasePlanProcessor):
    """Startup creation, innovation, tech ventures, fundraising."""

    category = "startup"
    display_name = "Startup & Innovation"

    domain_rules = """
- PROBLEM VALIDATION BEFORE SOLUTION: Validate the problem exists and is worth solving BEFORE building anything. Include 50+ customer discovery interviews as an early milestone.
- LEAN CANVAS: Create a lean canvas as the very first planning task. Revisit and update it monthly.
- MVP IN 4-8 WEEKS: First functional MVP must ship within 4-8 weeks. Scope ruthlessly — cut features, not quality.
- CUSTOMER DISCOVERY: Conduct minimum 50 customer discovery interviews before committing to a solution. Document insights systematically.
- METRICS TRACKING: Define and track key metrics from day 1 — CAC (Customer Acquisition Cost), LTV (Lifetime Value), churn rate, MRR/ARR, activation rate.
- FUNDING STRATEGY: Decide early: bootstrap vs raise. If raising, include pitch deck milestones, investor research, and networking tasks.
- PITCH DECK: Build and iterate on pitch deck. Include tasks for practice pitches and feedback rounds.
- LEGAL INCORPORATION: Include legal setup early (company registration, shareholder agreements, IP protection, terms of service).
- TEAM BUILDING: Include co-founder search or key hire milestones. Define roles, equity splits, and vesting schedules.
- PRODUCT-MARKET FIT INDICATORS: Define clear PMF signals (retention rate > 40%, NPS > 40, organic growth). Don't scale before PMF.
- PIVOT DECISION FRAMEWORK: Include regular pivot-or-persevere checkpoints (monthly). Define criteria for pivoting vs iterating.
- SCALING PLAN: Only plan scaling AFTER PMF is validated. Include infrastructure, hiring, and process milestones.
- ADVISORY BOARD: Include tasks to identify and recruit 2-3 advisors with relevant domain expertise.
"""

    extra_calibration_hints = """
- Ask about the specific problem they want to solve and for whom
- Ask about their technical skills and team (solo founder, co-founders, team)
- Ask about available funding and runway (savings, investment, revenue)
- Ask about market research already done (competitors, market size)
- Ask about their risk tolerance and timeline expectations
- Ask about previous startup or entrepreneurial experience
"""


class FreelanceProcessor(BasePlanProcessor):
    """Freelancing, independent consulting, self-employment."""

    category = "freelance"
    display_name = "Freelance & Indépendant"

    domain_rules = """
- PORTFOLIO/WEBSITE FIRST: Build a professional portfolio or website BEFORE actively seeking clients. Include testimonials and case studies.
- PRICING STRATEGY: Use value-based pricing, NOT hourly rates. Include tasks to research market rates and calculate minimum viable rate.
- CLIENT ACQUISITION FUNNEL: Build a systematic client acquisition funnel — cold outreach, content marketing, referral system, platform profiles.
- CONTRACT TEMPLATES: Create professional contract templates covering scope, payment terms, revisions, IP rights, and termination clauses.
- INVOICING SETUP: Set up invoicing and payment systems (Stripe, PayPal, bank transfer). Include tasks for payment follow-up processes.
- TAX MANAGEMENT: Include quarterly tax estimate calculations, expense tracking, and accountant consultation. Set aside 25-30% of revenue for taxes.
- TIME TRACKING: Implement time tracking from day 1 for profitability analysis and accurate project scoping.
- SPECIALIZATION NICHE: Define a clear niche/specialization. Generalists compete on price; specialists compete on value.
- REFERRAL SYSTEM: Build a referral system — include tasks to ask satisfied clients for referrals and testimonials.
- CLIENT COMMUNICATION PROTOCOLS: Establish communication boundaries (response times, meeting days, availability hours).
- PROJECT MANAGEMENT TOOLS: Set up project management tools (Notion, Trello, Asana) for client-facing project tracking.
- WORK-LIFE BOUNDARIES: Set clear boundaries — define working hours, dedicated workspace, and unplugging routines.
- EMERGENCY FUND: Build 3-6 months of expenses as emergency fund BEFORE going full-time freelance.
- INSURANCE: Include tasks to research and obtain professional liability insurance, health insurance, and retirement planning.
"""

    extra_calibration_hints = """
- Ask about their specific skill/service offering
- Ask about current employment status (transitioning or already freelance)
- Ask about existing client base or network
- Ask about financial runway and savings
- Ask about target income and lifestyle goals
- Ask about administrative/business skills (invoicing, contracts, taxes)
"""


class SideHustleProcessor(BasePlanProcessor):
    """Side projects, extra income, passive income alongside main employment."""

    category = "side_hustle"
    display_name = "Side Hustle & Revenus Complémentaires"

    domain_rules = """
- TIME AUDIT: Start with a time audit — identify exactly how many hours per week are available outside the main job. Plan within that constraint.
- MINIMUM VIABLE OFFERING: Define the simplest version of the offering that can generate revenue. Launch within 30 days.
- FIRST SALE WITHIN 30 DAYS: Prioritize getting the first sale/client within the first month. Revenue validates the idea faster than research.
- AUTOMATION FROM START: Automate repetitive tasks from the beginning (email sequences, payment processing, content scheduling). Time is the scarcest resource.
- PASSIVE VS ACTIVE INCOME BALANCE: Distinguish between active income (trading time for money) and passive income (products, digital assets). Aim to increase passive ratio over time.
- LEGAL COMPLIANCE: Check employment contract for non-compete and moonlighting clauses. Register as auto-entrepreneur or equivalent.
- TAX IMPLICATIONS: Include tasks to understand tax obligations for additional income. Set aside appropriate percentage from earnings.
- ENERGY MANAGEMENT: Plan around energy levels, not just time. Schedule creative work during peak energy. Include rest and recovery tasks to avoid burnout.
- SCALING TRIGGERS: Define clear metrics for when to consider going full-time (revenue > 70% of salary for 3+ months, growing demand, etc.).
- MULTIPLE INCOME STREAMS: After the first side hustle is stable, plan diversification into 2-3 income streams for resilience.
"""

    extra_calibration_hints = """
- Ask about current employment situation and available hours per week
- Ask about the specific side hustle idea or income stream
- Ask about existing skills that can be monetized
- Ask about initial budget available for the side hustle
- Ask about income goals (supplementary vs replacement income)
- Ask about energy levels and when they have the most productive time
"""


class EcommerceProcessor(BasePlanProcessor):
    """Online selling, e-commerce stores, marketplaces, dropshipping."""

    category = "ecommerce"
    display_name = "E-Commerce & Vente en Ligne"

    domain_rules = """
- NICHE VALIDATION: Validate demand AND competition before committing. Use tools like Google Trends, Amazon Best Sellers, and social media research.
- PLATFORM SELECTION: Choose the right platform based on budget and skills — Shopify (easy), WooCommerce (flexible), Etsy (handmade), Amazon FBA (scale).
- PRODUCT SOURCING: Include tasks for sourcing strategy — manufacturing, wholesale, dropshipping, or handmade. Get samples before committing.
- PHOTOGRAPHY/LISTING OPTIMIZATION: Professional product photos are non-negotiable. Include tasks for photography setup, SEO-optimized descriptions, and A/B testing titles.
- PRICING STRATEGY: Calculate all costs (product, shipping, platform fees, ads, returns) before setting prices. Target minimum 30% margin after all costs.
- SHIPPING LOGISTICS: Set up shipping strategy early — carriers, packaging, tracking, international shipping considerations.
- CUSTOMER SERVICE SETUP: Include tasks for customer service processes — FAQ, return policy, response templates, review management.
- MARKETING CHANNELS: Plan at least 3 marketing channels — SEO (long-term), social media (organic), paid ads (growth). Include content calendar.
- CONVERSION RATE OPTIMIZATION: Include tasks for optimizing product pages, checkout flow, and cart abandonment recovery.
- RETURN POLICY: Define clear return/refund policy. Include tasks for handling returns efficiently.
- INVENTORY MANAGEMENT: Set up inventory tracking system. Plan for stock levels, reorder points, and seasonal demand.
- ANALYTICS TRACKING: Set up Google Analytics, platform analytics, and conversion tracking from day 1. Review weekly.
"""

    extra_calibration_hints = """
- Ask about the specific product type or niche they want to sell
- Ask about budget available for initial inventory and marketing
- Ask about technical skills (website building, marketing, photography)
- Ask about whether they have an existing audience or starting from scratch
- Ask about fulfillment preferences (self-ship, dropship, third-party logistics)
- Ask about target market (local, national, international)
"""


class NonProfitProcessor(BasePlanProcessor):
    """Creating associations, NGOs, foundations, social enterprises."""

    category = "nonprofit"
    display_name = "Association & ONG"

    domain_rules = """
- MISSION STATEMENT CLARITY: Define a clear, compelling mission statement as the very first task. Everything else flows from the mission.
- LEGAL REGISTRATION: Include tasks for legal registration (association loi 1901, 501(c)(3), or equivalent). Understand bylaws, governance requirements, and reporting obligations.
- BOARD FORMATION: Recruit a diverse board of directors with complementary skills (legal, finance, marketing, domain expertise). Include governance training.
- FUNDING STRATEGY: Diversify funding sources — grants, individual donations, corporate sponsorships, fundraising events, membership fees. Never rely on a single source.
- VOLUNTEER RECRUITMENT: Include tasks for volunteer recruitment, onboarding, training, and retention programs. Define clear volunteer roles and expectations.
- IMPACT MEASUREMENT FRAMEWORK: Define measurable impact indicators from day 1. Include tasks for data collection and impact reporting.
- FINANCIAL TRANSPARENCY: Set up transparent financial management — bookkeeping, annual reports, public financial statements. Build trust through accountability.
- MARKETING/AWARENESS CAMPAIGNS: Include tasks for building awareness — website, social media presence, press outreach, storytelling, beneficiary testimonials.
- PARTNERSHIPS: Identify and build partnerships with complementary organizations, government agencies, and corporate partners.
- PROGRAM DESIGN: Design programs with clear goals, target beneficiaries, activities, timeline, and evaluation criteria.
- ANNUAL REPORTING: Include tasks for annual impact reports, financial audits, and donor communication.
- SUSTAINABILITY PLANNING: Plan for long-term financial sustainability — diversified revenue, reserve fund, earned income strategies.
"""

    extra_calibration_hints = """
- Ask about the specific cause or social issue they want to address
- Ask about their experience with nonprofit or volunteer work
- Ask about the target beneficiary group
- Ask about initial funding and resources available
- Ask about team or co-founders involved
- Ask about the geographic scope (local, national, international)
"""



class EmergencyPreparednessProcessor(BasePlanProcessor):
    """Emergency preparedness, prepping, survival skills, disaster readiness."""

    category = "prepping"
    display_name = "Préparation aux Urgences"

    domain_rules = """
- RISK ASSESSMENT FIRST: Start by assessing risks specific to the local area (floods, earthquakes, storms, industrial hazards, power outages). Prioritize preparations for the most likely scenarios.
- 72-HOUR KIT MINIMUM: Build a complete 72-hour emergency kit as the first tangible milestone. This is the baseline before expanding to longer-term preparedness.
- WATER STORAGE: Plan for 1 gallon (approximately 4 liters) per person per day minimum. Include storage containers, purification methods (filters, tablets, boiling), and rotation schedule.
- FOOD STORAGE ROTATION SYSTEM: Implement a FIFO (first in, first out) rotation system. Store what you eat, eat what you store. Include a tracking spreadsheet or app for expiration dates.
- FIRST AID KIT AND TRAINING: Build a comprehensive first aid kit AND complete a certified first aid/CPR course. Kit without knowledge is insufficient.
- COMMUNICATION PLAN: Establish a family communication plan with a designated meeting point (near home + out of area), emergency contact list, and out-of-area contact person.
- DOCUMENT COPIES: Maintain copies of critical documents in both cloud storage (encrypted) and physical waterproof container — IDs, insurance, medical records, property deeds, financial accounts.
- FINANCIAL EMERGENCY FUND: Build a cash reserve (small bills) in the emergency kit PLUS a separate liquid savings account covering 3-6 months of expenses.
- VEHICLE EMERGENCY KIT: Equip each vehicle with a separate emergency kit — jumper cables, flashlight, blanket, water, first aid, basic tools, phone charger.
- HOME SAFETY UPGRADES: Include tasks for smoke detectors, CO detectors, fire extinguishers, emergency lighting, and securing heavy furniture/water heater.
- SKILLS TRAINING: Include practical skills training — first aid certification, fire extinguisher use, basic home repair, water purification, food preservation techniques.
- PERIODIC DRILLS: Schedule quarterly family emergency drills (fire evacuation, shelter-in-place, communication plan test). Review and update plans after each drill.
- GRADUAL BUILDUP: Do NOT buy everything at once. Plan a progressive monthly budget for preparedness supplies. Prioritize by likelihood and impact of scenarios.
"""

    extra_calibration_hints = """
- Ask about geographic location and local natural disaster risks
- Ask about household size (adults, children, elderly, pets)
- Ask about current preparedness level (nothing, basic, intermediate)
- Ask about budget available for emergency preparedness
- Ask about living situation (house, apartment, urban, rural)
- Ask about any specific concerns or scenarios they want to prepare for
"""


class InstrumentMasteryProcessor(BasePlanProcessor):
    """Learning and mastering a musical instrument."""

    category = "instrument"
    display_name = "Maîtrise d'un Instrument"

    domain_rules = """
- TEACHER/METHOD BOOK SELECTION: Start by selecting an appropriate teacher (in-person or online) or a reputable method book series for the specific instrument and skill level.
- DAILY PRACTICE MINIMUM: Establish a non-negotiable daily practice routine — 20 minutes minimum for beginners, 45 minutes for intermediate, 1 hour+ for advanced players. Consistency beats marathon sessions.
- WARM-UP ROUTINE: Every practice session must begin with a warm-up (5-10 min) — long tones, stretches, slow scales. This prevents injury and improves tone quality.
- SCALE PRACTICE: Include dedicated scale and arpeggio practice in every session. Cover all major and minor keys progressively. Scales are the foundation of technique.
- SIGHT-READING: Include regular sight-reading exercises (at least 3 times per week). Start below current level and gradually increase difficulty.
- REPERTOIRE BUILDING: Maintain at least 3 pieces at different stages simultaneously — one being learned, one being polished, one performance-ready. Rotate regularly.
- RECORDING SELF WEEKLY: Record a practice session or piece performance weekly. Review recordings to identify issues that are missed in real-time.
- THEORY ALONGSIDE PRACTICE: Include music theory study (intervals, chords, keys, rhythm, form) alongside instrument practice. Theory makes practice more efficient.
- EAR TRAINING: Include ear training exercises (interval recognition, chord identification, melody transcription) at least twice per week.
- PERFORMANCE MILESTONES: Progress through performance milestones — play for a friend → play at a small gathering → perform at a recital → participate in a concert or open mic.
- EQUIPMENT MAINTENANCE: Include regular instrument maintenance tasks — cleaning, tuning, string changes, reed replacement, valve oiling, as appropriate for the instrument.
- GENRE EXPLORATION: After building fundamentals, explore different musical genres to develop versatility and find personal musical identity.
"""

    extra_calibration_hints = """
- Ask about which specific instrument they want to learn or improve
- Ask about current skill level (complete beginner, can play some songs, intermediate, advanced)
- Ask about access to the instrument (own one, need to buy, can rent)
- Ask about availability of teachers or willingness to self-study
- Ask about musical goals (play for fun, join a band, perform publicly, pass exams)
- Ask about daily time available for practice
"""


class VisualArtProcessor(BasePlanProcessor):
    """Painting, drawing, illustration, watercolor, and other visual arts."""

    category = "visual_art"
    display_name = "Arts Visuels"

    domain_rules = """
- FUNDAMENTALS DAILY: Dedicate time every practice session to fundamentals — gesture drawing (5-10 min), value studies, color mixing exercises. These are the scales of visual art.
- REFERENCE LIBRARY BUILDING: Build and organize a personal reference library (photos, textures, poses, color palettes). Include tasks for collecting and categorizing references.
- MEDIUM EXPLORATION THEN SPECIALIZATION: Explore multiple mediums early (pencil, charcoal, watercolor, oil, digital) then specialize in 1-2 after identifying strengths and preferences.
- SKETCHBOOK HABIT: Carry a sketchbook everywhere and sketch daily. Include a daily sketching task (minimum 15 minutes) regardless of other practice. Quantity builds skill.
- STUDY MASTERS: Include regular copy studies of master artworks (one per week). Analyze their composition, color, brushwork, and technique. Learn by doing, not just looking.
- CREATE ORIGINAL WORK WEEKLY: Produce at least one original piece per week alongside studies. Balance learning from others with developing a personal voice.
- ART COMMUNITY ENGAGEMENT: Join art communities (online or local). Include tasks for sharing work, participating in challenges, attending life drawing sessions or workshops.
- CRITIQUE SESSIONS: Include regular critique sessions — seek feedback from peers, teachers, or online communities. Learn to give and receive constructive criticism.
- EXHIBITION/PORTFOLIO MILESTONES: Set progressive milestones — complete a portfolio of 10 pieces → submit to a local exhibition → create an online portfolio → apply for shows or commissions.
- SUPPLY MANAGEMENT: Plan art supply purchases progressively. Start with student-grade materials, upgrade to artist-grade as skills develop. Do not overspend upfront.
- STUDIO SETUP: Include tasks for creating a dedicated workspace with proper lighting, storage, and ventilation (especially for oil painting or spray media).
- DIGITAL VS TRADITIONAL BALANCE: If interested in both, allocate specific time for each. Digital skills (Procreate, Photoshop, Clip Studio) complement traditional media.
- COMMISSION PREPARATION: For those aiming to sell, include tasks for pricing research, contract templates, social media presence, and client communication skills.
"""

    extra_calibration_hints = """
- Ask about current skill level and experience in visual arts
- Ask about preferred or desired medium (pencil, watercolor, oil, digital, etc.)
- Ask about available workspace and materials
- Ask about specific goals (personal enjoyment, portfolio, exhibitions, commissions, career)
- Ask about daily time available for art practice
- Ask about art influences and styles they admire
"""


class CollectingProcessor(BasePlanProcessor):
    """Collecting hobbies — cards, stamps, coins, figurines, vinyl, sneakers, etc."""

    category = "collecting"
    display_name = "Collection & Hobby"

    domain_rules = """
- DEFINE SCOPE: Start by clearly defining what to collect — specific era, brand, condition standards, sub-category. A focused collection is more valuable and manageable than an unfocused one.
- BUDGET ALLOCATION: Set a strict monthly collecting budget and stick to it. Include a budget tracking task. Never overspend on impulse — patience is key in collecting.
- AUTHENTICATION KNOWLEDGE: Include tasks for learning authentication and grading standards specific to the collectible type. Know how to spot fakes, reproductions, and misrepresented items.
- STORAGE/DISPLAY SOLUTION: Plan proper storage and display from the start — archival sleeves, climate control, UV-protective cases, dust-free shelving as appropriate to the items.
- CATALOG/DATABASE SYSTEM: Set up a digital catalog or database system to track every item — acquisition date, price paid, condition, provenance, current value. Spreadsheet or dedicated app.
- COMMUNITY/CLUB JOINING: Join collector communities, clubs, and forums (online and local). Include tasks for attending swap meets, conventions, and collector events.
- MARKET KNOWLEDGE: Include tasks for studying market trends, pricing guides, auction results, and rarity scales. Understand what drives value in the specific collecting niche.
- CONDITION GRADING: Learn and apply the standard grading system for the collectible type (PSA for cards, NGC for coins, VG+ for vinyl, etc.). Condition is everything.
- INSURANCE FOR VALUABLE COLLECTIONS: Once the collection reaches significant value, include tasks for getting it appraised and properly insured. Document everything with photos.
- BUYING STRATEGY: Develop a buying strategy — research auctions, trusted dealers, online marketplaces, estate sales. Include tasks for vetting sellers and comparing prices.
- TRADING ETIQUETTE: Learn trading norms and etiquette in the community. Include tasks for building trading relationships and maintaining a good reputation.
- DISPLAYING/SHARING: Include tasks for sharing the collection — create an online showcase, participate in exhibitions, write about items, or contribute to collector resources.
"""

    extra_calibration_hints = """
- Ask about what they want to collect or already collect
- Ask about current collection size and value
- Ask about monthly budget available for collecting
- Ask about storage space available
- Ask about collecting goals (personal enjoyment, investment, completing a set, historical preservation)
- Ask about experience with buying, selling, or trading collectibles
"""


class UrbanFarmingProcessor(BasePlanProcessor):
    """Urban farming, balcony gardening, hydroponics, microgreens, city agriculture."""

    category = "urban_farming"
    display_name = "Agriculture Urbaine"

    domain_rules = """
- SPACE ASSESSMENT: Start by thoroughly assessing available space — balcony dimensions, rooftop access, indoor areas, windowsills. Measure and photograph everything.
- LIGHT ANALYSIS: Analyze sunlight exposure for each potential growing area — hours of direct sun, direction faced, seasonal changes. Use a light meter or track manually for a week.
- CONTAINER SELECTION: Choose appropriate containers based on space and crops — fabric pots, railing planters, vertical towers, window boxes. Ensure proper drainage in all containers.
- SOIL/SUBSTRATE PREPARATION: Select the right growing medium — lightweight potting mix for balconies (not garden soil), coco coir for hydroponics, specialized mixes for specific crops. Include tasks for soil testing and amendment.
- SEED STARTING CALENDAR: Create a planting calendar adapted to the local climate and available space. Include indoor seed starting dates, transplant dates, and succession planting schedule.
- VERTICAL GARDENING FOR SMALL SPACES: Maximize limited space with vertical solutions — trellises, wall planters, stacking systems, hanging baskets. Include tasks for building or installing vertical structures.
- COMPOSTING: Set up composting appropriate to the urban setting — vermicomposting (worm bin) for apartments, bokashi for odorless indoor composting, or tumbler for balconies.
- WATERING SYSTEM: Install an efficient watering system — drip irrigation with timer for balconies, self-watering containers, or wicking beds. Overwatering and underwatering are the top urban garden killers.
- PEST MANAGEMENT: Use integrated pest management suited to urban settings — companion planting, neem oil spray, beneficial insects, physical barriers (netting, row covers). Avoid toxic pesticides in small spaces.
- HARVEST SCHEDULE: Include a harvest tracking schedule. Learn harvest indicators for each crop to pick at peak quality. Include tasks for preserving excess harvest (drying, freezing, fermenting).
- SUCCESSION PLANTING: Plan continuous yields through succession planting — sow new seeds every 2-3 weeks for salad greens, herbs, and fast-growing crops.
- COMMUNITY GARDEN: If private space is insufficient, include tasks for finding and joining a community garden. Research local availability and rules.
- LOCAL REGULATIONS CHECK: Include a task to check local regulations — building codes for rooftop structures, HOA rules for balcony gardens, water usage restrictions, composting regulations.
"""

    extra_calibration_hints = """
- Ask about available growing space (balcony, rooftop, indoor, windowsill, community garden)
- Ask about sunlight exposure and direction the space faces
- Ask about what they want to grow (herbs, vegetables, fruits, microgreens)
- Ask about previous gardening or farming experience
- Ask about budget for setup (containers, soil, seeds, irrigation)
- Ask about time available for daily garden maintenance
"""


class InvestingProcessor(BasePlanProcessor):
    """Stock market, ETFs, bonds, portfolio management, long-term investing."""

    category = "investing"
    display_name = "Investissement & Bourse"

    domain_rules = """
- FINANCIAL LITERACY FIRST: Before any investment, complete financial literacy fundamentals (how markets work, asset classes, risk vs return).
- PAPER TRADING FIRST: Practice with simulated trading for a minimum of 3 months before investing real money.
- RISK ASSESSMENT: Complete a thorough risk tolerance assessment before building any portfolio.
- DIVERSIFICATION: Diversify across asset classes (stocks, bonds, real estate, commodities). Never concentrate in one sector or stock.
- INDEX FUNDS FOR BEGINNERS: Start with low-cost index funds (S&P 500, MSCI World). Avoid individual stock picking until experienced.
- DOLLAR-COST AVERAGING: Invest fixed amounts at regular intervals rather than timing the market. Set up automatic recurring investments.
- EMERGENCY FUND PREREQUISITE: Must have 3-6 months of expenses saved before investing any money.
- TAX-ADVANTAGED ACCOUNTS FIRST: Prioritize tax-advantaged accounts (PEA, assurance-vie, 401k, ISA) before taxable brokerage accounts.
- REBALANCING SCHEDULE: Include quarterly or semi-annual portfolio rebalancing tasks to maintain target allocation.
- NEVER INVEST WHAT YOU CAN'T AFFORD TO LOSE: All invested money must be money you won't need for at least 5 years.
- FUNDAMENTAL VS TECHNICAL ANALYSIS: Learn basics of both approaches. Fundamental for long-term, technical for entry/exit timing.
- LONG-TERM MINDSET: Ignore daily market fluctuations. Check portfolio maximum once per month. Plan for 10+ year horizon.
- PROFESSIONAL ADVISOR: For portfolios exceeding 100K€, include a task to consult a certified financial advisor or wealth manager.
"""

    extra_calibration_hints = """
- Ask about current investment experience (complete beginner, some knowledge, experienced)
- Ask about investable amount and monthly contribution capacity
- Ask about investment timeline and liquidity needs
- Ask about risk tolerance (conservative, moderate, aggressive)
- Ask about existing portfolio or retirement accounts
- Ask about financial goals (retirement, wealth building, specific purchase)
"""


class CryptoBlockchainProcessor(BasePlanProcessor):
    """Bitcoin, Ethereum, DeFi, NFTs, Web3, blockchain technology."""

    category = "crypto"
    display_name = "Crypto & Blockchain"

    domain_rules = """
- BLOCKCHAIN FUNDAMENTALS FIRST: Understand how blockchain works, consensus mechanisms, and smart contracts before any trading.
- SECURITY FIRST: Set up a hardware wallet, enable 2FA on all exchanges, securely back up seed phrase offline. NEVER share private keys.
- START WITH ESTABLISHED COINS: Begin with BTC and ETH only. Avoid altcoins until you understand market dynamics thoroughly.
- SMALL AMOUNTS ONLY INITIALLY: First 3 months, invest only amounts you are 100% prepared to lose completely.
- NEVER INVEST MORE THAN YOU CAN LOSE: Crypto is highly volatile. Limit crypto allocation to a small percentage of total portfolio (5-15%).
- DCA STRATEGY: Use dollar-cost averaging for accumulation. Never try to time the crypto market.
- TAX TRACKING FROM DAY 1: Track every transaction from the very first trade. Use crypto tax software (Koinly, CoinTracker). Understand local tax rules.
- SCAM AWARENESS: Learn to identify rug pulls, phishing attacks, fake airdrops, and Ponzi schemes. If it promises guaranteed returns, it's a scam.
- DECENTRALIZED VS CENTRALIZED EXCHANGES: Understand the tradeoffs. Use reputable CEXs (Binance, Kraken, Coinbase) for beginners. Learn DEXs later.
- YIELD FARMING RISKS: Understand impermanent loss, smart contract risks, and rug pull risks before any DeFi participation.
- REGULATORY COMPLIANCE: Stay informed on local crypto regulations. Declare all holdings and gains as required by law.
- PORTFOLIO TRACKING TOOLS: Set up portfolio tracking (CoinGecko, Delta, Zerion) from day one. Monitor allocation, not daily prices.
"""

    extra_calibration_hints = """
- Ask about current crypto knowledge (never heard of it, knows basics, has traded before)
- Ask about amount they plan to invest in crypto
- Ask about specific interest (trading, long-term holding, DeFi, NFTs, building on blockchain)
- Ask about technical comfort level (comfortable with wallets and keys, or not)
- Ask about risk tolerance specific to crypto volatility
- Ask about existing crypto holdings if any
"""


class EarlyRetirementFIREProcessor(BasePlanProcessor):
    """Financial independence, early retirement, FIRE movement, aggressive saving."""

    category = "fire"
    display_name = "FIRE & Retraite Anticipée"

    domain_rules = """
- CALCULATE FIRE NUMBER: First task must be calculating the FIRE number (25x annual expenses). This is the target portfolio size.
- SAVINGS RATE IS KEY: Track and optimize savings rate as the primary metric. Higher savings rate = earlier retirement. Target 50%+ for aggressive FIRE.
- EXPENSE OPTIMIZATION BEFORE INCOME OPTIMIZATION: Cut expenses first (housing, transport, food, subscriptions) before focusing on income increase.
- INVESTMENT STRATEGY: Build a portfolio of low-cost index funds and/or real estate. Keep investment fees under 0.3% annually.
- 4% RULE UNDERSTANDING: Understand the Trinity Study and safe withdrawal rate. Include tasks to model different withdrawal scenarios.
- FIRE VARIANTS: Determine which FIRE path fits — Coast FIRE (stop saving, let compound growth work), Lean FIRE (<40K/year expenses), Fat FIRE (>100K/year expenses).
- HEALTHCARE PLANNING: Include tasks to plan for healthcare coverage after leaving employment. This is often the biggest FIRE obstacle.
- SOCIAL FULFILLMENT POST-RETIREMENT: Include tasks to develop hobbies, community, and purpose beyond work BEFORE retiring.
- TEST PERIODS: Include mini-retirement experiments (sabbatical, unpaid leave) to test the lifestyle before committing fully.
- TAX OPTIMIZATION: Include tasks for Roth conversion ladders, capital gains harvesting, and tax-efficient withdrawal strategies.
- SPOUSE ALIGNMENT: If partnered, include tasks for regular financial discussions and goal alignment with spouse/partner.
- GEOGRAPHIC ARBITRAGE: Evaluate cost-of-living differences. Consider relocating to lower-cost areas to accelerate FIRE timeline.
- WITHDRAWAL STRATEGY: Plan the specific order of account withdrawals (taxable → tax-deferred → tax-free) for tax efficiency.
"""

    extra_calibration_hints = """
- Ask about current annual income and expenses
- Ask about current savings rate and net worth
- Ask about target retirement age and desired lifestyle
- Ask about current investments and retirement accounts
- Ask about family situation (single, partner, dependents)
- Ask about willingness to make lifestyle changes (housing, location, spending)
"""


class DebtFreeProcessor(BasePlanProcessor):
    """Debt payoff, credit management, loan repayment, financial recovery."""

    category = "debt_free"
    display_name = "Zéro Dettes"

    domain_rules = """
- LIST ALL DEBTS: First task must be creating a complete debt inventory (creditor, total amount, interest rate, minimum monthly payment, due dates).
- SNOWBALL OR AVALANCHE: Choose a payoff method — Snowball (smallest balance first for quick wins) or Avalanche (highest interest first for math optimization). Stick with one.
- BUDGET CREATION: Create a detailed monthly budget before any aggressive payoff. Know exactly where every euro goes.
- EMERGENCY MINI-FUND FIRST: Build a small emergency fund (1000€) before aggressive debt payoff to avoid new debt from emergencies.
- NEGOTIATE INTEREST RATES: Include tasks to call each creditor and negotiate lower interest rates. Even 1-2% reduction saves significantly.
- CONSOLIDATION EVALUATION: Include a task to evaluate whether debt consolidation or balance transfers make mathematical sense.
- AVOID NEW DEBT COMMITMENT: Commit to zero new debt during the payoff period. Cut up credit cards if necessary. Cash-only for discretionary spending.
- CELEBRATION MILESTONES: Celebrate each debt paid off (small, budget-friendly reward). Mark each payoff as a major milestone in the plan.
- CREDIT SCORE MONITORING: Include monthly credit score check tasks. Track improvements as debts are paid off.
- LIFESTYLE ADJUSTMENT: Identify and include specific lifestyle changes (cancel subscriptions, meal prep, reduce dining out, sell unused items).
- INCOME INCREASE STRATEGIES: Include tasks to explore additional income (overtime, side gig, selling items, freelancing) to accelerate payoff.
- ACCOUNTABILITY PARTNER: Include tasks to find and regularly check in with a financial accountability partner or debt-free community.
"""

    extra_calibration_hints = """
- Ask about total debt amount and number of debts
- Ask about types of debt (credit cards, student loans, car loan, mortgage, personal loans)
- Ask about current monthly income and expenses
- Ask about minimum monthly debt payments vs available extra payment capacity
- Ask about previous debt payoff attempts and what went wrong
- Ask about willingness to make lifestyle sacrifices for faster payoff
"""


class PassiveIncomeProcessor(BasePlanProcessor):
    """Passive income streams, digital products, rental income, dividends, online business."""

    category = "passive_income"
    display_name = "Revenus Passifs"

    domain_rules = """
- NO TRULY PASSIVE INCOME: All passive income requires significant upfront work, time, or capital investment. Set realistic expectations from the start.
- REALISTIC TIMELINE: Plan for 6-18 months before generating meaningful income from a new stream. First dollar is the hardest.
- ONE STREAM AT A TIME: Focus on building and stabilizing one income stream before starting another. Spreading thin leads to failure.
- VALIDATE BEFORE BUILDING: Include market validation tasks (surveys, landing pages, pre-sales) before investing months of effort.
- CONTENT VS RENTAL VS DIVIDENDS: Help choose the right type — digital products/content (low capital, high time), rental income (high capital, moderate time), dividend investing (high capital, low time).
- AUTOMATION SETUP: Include specific tasks for automating delivery, payment collection, customer service, and marketing funnels.
- LEGAL STRUCTURE: Include tasks for proper business registration, contracts, terms of service, and intellectual property protection.
- TAX IMPLICATIONS: Include tasks to understand and plan for tax obligations on passive income (self-employment tax, rental income tax, capital gains).
- REINVESTMENT STRATEGY: Plan to reinvest 50-80% of initial passive income back into growth before taking profits for personal use.
- DIVERSIFICATION AFTER STABILITY: Only diversify into additional streams after the first stream generates consistent income for 3+ months.
- SCALE BEFORE NEW STREAMS: Optimize and scale the first stream (improve conversion, expand audience, raise prices) before adding complexity.
"""

    extra_calibration_hints = """
- Ask about available capital to invest upfront
- Ask about available time per week to build the income stream
- Ask about existing skills or expertise that could be monetized
- Ask about preferred passive income type (digital products, rental, investments, content)
- Ask about income target (monthly amount and timeline)
- Ask about current employment situation (building alongside a job or full-time focus)
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
    "home_renovation": HomeRenovationProcessor(),
    "renovation": HomeRenovationProcessor(),
    "diy": DIYCraftProcessor(),
    "craft": DIYCraftProcessor(),
    "parenting": ParentingProcessor(),
    "family": ParentingProcessor(),
    "pets": PetCareProcessor(),
    "animals": PetCareProcessor(),
    "gardening": GardeningProcessor(),
    "agriculture": GardeningProcessor(),
    "real_estate": RealEstateProcessor(),
    "property": RealEstateProcessor(),
    "retirement": RetirementProcessor(),
    "pension": RetirementProcessor(),
    "volunteer": VolunteerProcessor(),
    "humanitarian": VolunteerProcessor(),
    "sobriety": SobrietyRecoveryProcessor(),
    "recovery": SobrietyRecoveryProcessor(),
    "environmental": EnvironmentalProcessor(),
    "ecology": EnvironmentalProcessor(),
    "endurance": MarathonEnduranceProcessor(),
    "race": MarathonEnduranceProcessor(),
    "marathon": MarathonEnduranceProcessor(),
    "martial_arts": MartialArtsProcessor(),
    "combat": MartialArtsProcessor(),
    "dance": DanceProcessor(),
    "dancing": DanceProcessor(),
    "outdoor": OutdoorSurvivalProcessor(),
    "survival": OutdoorSurvivalProcessor(),
    "body_transformation": BodyTransformationProcessor(),
    "physique": BodyTransformationProcessor(),
    "mental_health": MentalHealthProcessor(),
    "mental": MentalHealthProcessor(),
    "sleep": SleepOptimizationProcessor(),
    "insomnia": SleepOptimizationProcessor(),
    "aging": HealthyAgingProcessor(),
    "senior": HealthyAgingProcessor(),
    "weight_management": WeightManagementProcessor(),
    "weight": WeightManagementProcessor(),
    "fertility": FertilityPregnancyProcessor(),
    "pregnancy": FertilityPregnancyProcessor(),
    "music_production": MusicProductionProcessor(),
    "beatmaking": MusicProductionProcessor(),
    "writing": CreativeWritingProcessor(),
    "publishing": CreativeWritingProcessor(),
    "fashion": FashionStyleProcessor(),
    "style": FashionStyleProcessor(),
    "public_speaking": PublicSpeakingProcessor(),
    "speaking": PublicSpeakingProcessor(),
    "content_creation": ContentCreationProcessor(),
    "influencer": ContentCreationProcessor(),
    "minimalism": MinimalismProcessor(),
    "declutter": MinimalismProcessor(),
    "digital_detox": DigitalDetoxProcessor(),
    "screen_time": DigitalDetoxProcessor(),
    "organization": HomeOrganizationProcessor(),
    "home_organization": HomeOrganizationProcessor(),
    "emigration": EmigrationProcessor(),
    "expat": EmigrationProcessor(),
    "immigration": EmigrationProcessor(),
    "event_planning": EventPlanningProcessor(),
    "event": EventPlanningProcessor(),
    "wedding": EventPlanningProcessor(),
    "social_media": SocialMediaGrowthProcessor(),
    "influencer": SocialMediaGrowthProcessor(),
    "podcast": PodcastProcessor(),
    "podcasting": PodcastProcessor(),
    "app_dev": AppDevelopmentProcessor(),
    "app_development": AppDevelopmentProcessor(),
    "book": BookWritingProcessor(),
    "writing_book": BookWritingProcessor(),
    "online_course": OnlineCourseProcessor(),
    "course": OnlineCourseProcessor(),
    "research": AcademicResearchProcessor(),
    "thesis": AcademicResearchProcessor(),
    "dissertation": AcademicResearchProcessor(),
    "competitive_exam": CompetitiveExamProcessor(),
    "concours": CompetitiveExamProcessor(),
    "data_science": DataScienceAIProcessor(),
    "machine_learning": DataScienceAIProcessor(),
    "cybersecurity": CybersecurityProcessor(),
    "infosec": CybersecurityProcessor(),
    "hacking": CybersecurityProcessor(),
    "teaching": TeachingMentoringProcessor(),
    "mentoring": TeachingMentoringProcessor(),
    "tutoring": TeachingMentoringProcessor(),
    "automotive": AutomotiveProcessor(),
    "mechanic": AutomotiveProcessor(),
    "gaming": GamingEsportsProcessor(),
    "esports": GamingEsportsProcessor(),
    "culinary": AdvancedCookingProcessor(),
    "gastronomy": AdvancedCookingProcessor(),
    "photography": PhotographyVideoProcessor(),
    "videography": PhotographyVideoProcessor(),
    "spirituality": SpiritualityMindfulnessProcessor(),
    "mindfulness": SpiritualityMindfulnessProcessor(),
    "relocation": RelocationProcessor(),
    "moving": RelocationProcessor(),
    "wedding": WeddingPlanningProcessor(),
    "nuptials": WeddingPlanningProcessor(),
    "car_purchase": CarPurchaseProcessor(),
    "vehicle": CarPurchaseProcessor(),
    "immersion": LanguageImmersionProcessor(),
    "study_abroad": LanguageImmersionProcessor(),
    "digital_nomad": DigitalNomadProcessor(),
    "nomad": DigitalNomadProcessor(),
    "driving": DrivingLicenseProcessor(),
    "driving_license": DrivingLicenseProcessor(),
    "extreme_sports": ExtremeSportsProcessor(),
    "extreme": ExtremeSportsProcessor(),
    "retirement_hobby": RetirementHobbyProcessor(),
    "senior_hobby": RetirementHobbyProcessor(),
    "competition": CompetitionPrepProcessor(),
    "championship": CompetitionPrepProcessor(),
    "life_transition": LifeTransitionProcessor(),
    "transition": LifeTransitionProcessor(),
    "dating": DatingProcessor(),
    "seduction": DatingProcessor(),
    "confidence": ConfidenceProcessor(),
    "self_esteem": ConfidenceProcessor(),
    "leadership": LeadershipProcessor(),
    "management": LeadershipProcessor(),
    "networking": NetworkingProcessor(),
    "professional_network": NetworkingProcessor(),
    "communication": CommunicationProcessor(),
    "expression": CommunicationProcessor(),
    "startup": StartupProcessor(),
    "innovation": StartupProcessor(),
    "freelance": FreelanceProcessor(),
    "independent": FreelanceProcessor(),
    "side_hustle": SideHustleProcessor(),
    "extra_income": SideHustleProcessor(),
    "ecommerce": EcommerceProcessor(),
    "online_store": EcommerceProcessor(),
    "nonprofit": NonProfitProcessor(),
    "association": NonProfitProcessor(),
    "prepping": EmergencyPreparednessProcessor(),
    "emergency": EmergencyPreparednessProcessor(),
    "instrument": InstrumentMasteryProcessor(),
    "instrument_mastery": InstrumentMasteryProcessor(),
    "visual_art": VisualArtProcessor(),
    "painting": VisualArtProcessor(),
    "collecting": CollectingProcessor(),
    "collector": CollectingProcessor(),
    "urban_farming": UrbanFarmingProcessor(),
    "urban_garden": UrbanFarmingProcessor(),
    "investing": InvestingProcessor(),
    "stock_market": InvestingProcessor(),
    "crypto": CryptoBlockchainProcessor(),
    "blockchain": CryptoBlockchainProcessor(),
    "fire": EarlyRetirementFIREProcessor(),
    "early_retirement": EarlyRetirementFIREProcessor(),
    "debt_free": DebtFreeProcessor(),
    "debt": DebtFreeProcessor(),
    "passive_income": PassiveIncomeProcessor(),
    "passive": PassiveIncomeProcessor(),
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
        # Spanish (es)
        "correr", "gimnasio", "perder peso", "ejercicio", "adelgazar",
        # Portuguese (pt)
        "academia", "perder peso", "exercício", "emagrecer", "musculação",
        # German (de)
        "laufen", "abnehmen", "fitnessstudio", "gesundheit", "übung",
        # Italian (it)
        "correre", "palestra", "perdere peso", "esercizio", "dimagrire",
        # Dutch (nl)
        "hardlopen", "sportschool", "afvallen", "gezondheid", "oefening",
        # Russian (ru)
        "бег", "спортзал", "похудеть", "здоровье", "тренировка",
        # Polish (pl)
        "bieganie", "siłownia", "schudnąć", "zdrowie", "ćwiczenia",
        # Turkish (tr)
        "koşmak", "spor salonu", "kilo vermek", "sağlık", "egzersiz",
        # Japanese (ja)
        "ランニング", "ダイエット", "筋トレ", "健康", "運動",
        # Korean (ko)
        "달리기", "헬스장", "다이어트", "건강", "운동",
        # Chinese (zh)
        "跑步", "健身房", "减肥", "健康", "锻炼",
        # Arabic (ar)
        "جري", "صالة رياضية", "إنقاص الوزن", "صحة", "تمارين",
        # Hindi (hi)
        "दौड़ना", "जिम", "वजन कम करना", "स्वास्थ्य", "व्यायाम",
        # Haitian Creole (ht)
        "kouri", "jimnastik", "pèdi pwa", "sante", "egzèsis",
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
        # Spanish (es)
        "dinero", "invertir", "ahorrar", "bolsa", "finanzas",
        # Portuguese (pt)
        "dinheiro", "investir", "poupar", "bolsa de valores", "finanças",
        # German (de)
        "geld", "investieren", "sparen", "börse", "finanzen",
        # Italian (it)
        "soldi", "investire", "risparmiare", "borsa", "finanza",
        # Dutch (nl)
        "geld", "beleggen", "sparen", "beurs", "financiën",
        # Russian (ru)
        "деньги", "инвестировать", "сбережения", "биржа", "финансы",
        # Polish (pl)
        "pieniądze", "inwestować", "oszczędzać", "giełda", "finanse",
        # Turkish (tr)
        "para", "yatırım", "birikim", "borsa", "finans",
        # Japanese (ja)
        "お金", "投資", "貯金", "株式", "金融",
        # Korean (ko)
        "돈", "투자", "저축", "주식", "금융",
        # Chinese (zh)
        "钱", "投资", "储蓄", "股票", "金融",
        # Arabic (ar)
        "مال", "استثمار", "ادخار", "بورصة", "مالية",
        # Hindi (hi)
        "पैसा", "निवेश", "बचत", "शेयर बाजार", "वित्त",
        # Haitian Creole (ht)
        "lajan", "envesti", "ekonomize", "labous", "finans",
    ],
    "career": [
        "business",
        "entreprise",
        "boutique",
        "commerce",
        "carrière",
        "career",
        "promotion",
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
        # Spanish (es)
        "negocio", "empresa", "empleo", "trabajo", "carrera",
        # Portuguese (pt)
        "negócio", "empresa", "emprego", "trabalho", "carreira",
        # German (de)
        "geschäft", "unternehmen", "beruf", "arbeit", "karriere",
        # Italian (it)
        "affari", "azienda", "lavoro", "impiego", "carriera",
        # Dutch (nl)
        "bedrijf", "onderneming", "baan", "werk", "carrière",
        # Russian (ru)
        "бизнес", "компания", "работа", "карьера", "зарплата",
        # Polish (pl)
        "biznes", "firma", "praca", "kariera", "pensja",
        # Turkish (tr)
        "iş", "şirket", "kariyer", "maaş", "girişimci",
        # Japanese (ja)
        "ビジネス", "会社", "仕事", "キャリア", "起業",
        # Korean (ko)
        "사업", "회사", "직업", "커리어", "창업",
        # Chinese (zh)
        "生意", "公司", "工作", "职业", "创业",
        # Arabic (ar)
        "عمل", "شركة", "وظيفة", "مهنة", "راتب",
        # Hindi (hi)
        "व्यापार", "कंपनी", "नौकरी", "करियर", "वेतन",
        # Haitian Creole (ht)
        "biznis", "antrepriz", "travay", "karyè", "salè",
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
        # Spanish (es)
        "idioma", "aprender inglés", "hablar", "vocabulario", "gramática",
        # Portuguese (pt)
        "idioma", "aprender inglês", "falar", "vocabulário", "gramática",
        # German (de)
        "sprache", "englisch lernen", "sprechen", "vokabeln", "grammatik",
        # Italian (it)
        "lingua", "imparare inglese", "parlare", "vocabolario", "grammatica",
        # Dutch (nl)
        "taal", "engels leren", "spreken", "woordenschat", "grammatica",
        # Russian (ru)
        "язык", "учить английский", "говорить", "словарный запас", "грамматика",
        # Polish (pl)
        "język", "uczyć się angielskiego", "mówić", "słownictwo", "gramatyka",
        # Turkish (tr)
        "dil", "ingilizce öğrenmek", "konuşmak", "kelime", "dilbilgisi",
        # Japanese (ja)
        "言語", "英語を学ぶ", "話す", "語彙", "文法",
        # Korean (ko)
        "언어", "영어 배우기", "말하기", "어휘", "문법",
        # Chinese (zh)
        "语言", "学英语", "说话", "词汇", "语法",
        # Arabic (ar)
        "لغة", "تعلم الإنجليزية", "تحدث", "مفردات", "قواعد",
        # Hindi (hi)
        "भाषा", "अंग्रेजी सीखना", "बोलना", "शब्दावली", "व्याकरण",
        # Haitian Creole (ht)
        "lang", "aprann anglè", "pale", "vokabilè", "gramè",
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
        # Spanish (es)
        "guitarra", "cantar", "pintar", "dibujar", "cocinar",
        # Portuguese (pt)
        "violão", "cantar", "pintar", "desenhar", "cozinhar",
        # German (de)
        "gitarre", "singen", "malen", "zeichnen", "kochen",
        # Italian (it)
        "chitarra", "cantare", "dipingere", "disegnare", "cucinare",
        # Dutch (nl)
        "gitaar", "zingen", "schilderen", "tekenen", "koken",
        # Russian (ru)
        "гитара", "петь", "рисовать", "танцевать", "готовить",
        # Polish (pl)
        "gitara", "śpiewać", "malować", "rysować", "gotować",
        # Turkish (tr)
        "gitar", "şarkı söylemek", "resim yapmak", "çizmek", "yemek yapmak",
        # Japanese (ja)
        "ギター", "歌う", "絵を描く", "料理", "ピアノ",
        # Korean (ko)
        "기타", "노래하기", "그림 그리기", "요리", "피아노",
        # Chinese (zh)
        "吉他", "唱歌", "画画", "烹饪", "钢琴",
        # Arabic (ar)
        "غيتار", "غناء", "رسم", "طبخ", "موسيقى",
        # Hindi (hi)
        "गिटार", "गाना", "चित्रकारी", "खाना बनाना", "संगीत",
        # Haitian Creole (ht)
        "gita", "chante", "pentire", "desine", "kwizin",
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
        # Spanish (es)
        "hábito", "confianza", "leer", "mejorar", "autoestima",
        # Portuguese (pt)
        "hábito", "confiança", "ler", "melhorar", "autoestima",
        # German (de)
        "gewohnheit", "selbstvertrauen", "lesen", "verbessern", "selbstwert",
        # Italian (it)
        "abitudine", "fiducia", "leggere", "migliorare", "autostima",
        # Dutch (nl)
        "gewoonte", "zelfvertrouwen", "lezen", "verbeteren", "zelfbeeld",
        # Russian (ru)
        "привычка", "уверенность", "читать", "улучшить", "самооценка",
        # Polish (pl)
        "nawyk", "pewność siebie", "czytać", "poprawić", "samoocena",
        # Turkish (tr)
        "alışkanlık", "özgüven", "okumak", "geliştirmek", "kişisel gelişim",
        # Japanese (ja)
        "習慣", "自信", "読書", "自己啓発", "目標",
        # Korean (ko)
        "습관", "자신감", "독서", "자기계발", "목표",
        # Chinese (zh)
        "习惯", "自信", "阅读", "自我提升", "目标",
        # Arabic (ar)
        "عادة", "ثقة بالنفس", "قراءة", "تطوير الذات", "أهداف",
        # Hindi (hi)
        "आदत", "आत्मविश्वास", "पढ़ना", "आत्म सुधार", "लक्ष्य",
        # Haitian Creole (ht)
        "abitid", "konfyans", "li", "amelyore", "objektif",
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
        # Spanish (es)
        "amigo", "relación", "pareja", "familia", "conocer gente",
        # Portuguese (pt)
        "amigo", "relacionamento", "casal", "família", "conhecer pessoas",
        # German (de)
        "freund", "beziehung", "partner", "familie", "leute kennenlernen",
        # Italian (it)
        "amico", "relazione", "coppia", "famiglia", "conoscere persone",
        # Dutch (nl)
        "vriend", "relatie", "partner", "familie", "mensen ontmoeten",
        # Russian (ru)
        "друг", "отношения", "партнёр", "семья", "знакомства",
        # Polish (pl)
        "przyjaciel", "związek", "partner", "rodzina", "poznać ludzi",
        # Turkish (tr)
        "arkadaş", "ilişki", "partner", "aile", "insanlarla tanışmak",
        # Japanese (ja)
        "友達", "人間関係", "パートナー", "家族", "出会い",
        # Korean (ko)
        "친구", "인간관계", "파트너", "가족", "만남",
        # Chinese (zh)
        "朋友", "人际关系", "伴侣", "家庭", "社交",
        # Arabic (ar)
        "صديق", "علاقة", "شريك", "عائلة", "تعارف",
        # Hindi (hi)
        "दोस्त", "रिश्ते", "साथी", "परिवार", "लोगों से मिलना",
        # Haitian Creole (ht)
        "zanmi", "relasyon", "patnè", "fanmi", "rankontre moun",
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
        # Spanish (es)
        "programación", "desarrollador", "aplicación", "informática", "tecnología",
        # Portuguese (pt)
        "programação", "desenvolvedor", "aplicativo", "informática", "tecnologia",
        # German (de)
        "programmierung", "entwickler", "anwendung", "informatik", "technologie",
        # Italian (it)
        "programmazione", "sviluppatore", "applicazione", "informatica", "tecnologia",
        # Dutch (nl)
        "programmeren", "ontwikkelaar", "applicatie", "informatica", "technologie",
        # Russian (ru)
        "программирование", "разработчик", "приложение", "информатика", "технологии",
        # Polish (pl)
        "programowanie", "programista", "aplikacja", "informatyka", "technologia",
        # Turkish (tr)
        "programlama", "geliştirici", "uygulama", "bilişim", "teknoloji",
        # Japanese (ja)
        "プログラミング", "開発者", "アプリ", "情報技術", "テクノロジー",
        # Korean (ko)
        "프로그래밍", "개발자", "앱", "정보기술", "기술",
        # Chinese (zh)
        "编程", "开发者", "应用", "信息技术", "技术",
        # Arabic (ar)
        "برمجة", "مطور", "تطبيق", "تكنولوجيا", "حاسوب",
        # Hindi (hi)
        "प्रोग्रामिंग", "डेवलपर", "ऐप", "सूचना प्रौद्योगिकी", "तकनीक",
        # Haitian Creole (ht)
        "pwogramasyon", "devlopè", "aplikasyon", "enfòmatik", "teknoloji",
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
        # Spanish (es)
        "viaje", "viajar", "mochilero", "senderismo", "excursión",
        # Portuguese (pt)
        "viagem", "viajar", "mochileiro", "trilha", "caminhada",
        # German (de)
        "reise", "reisen", "wandern", "rucksack", "abenteuer",
        # Italian (it)
        "viaggio", "viaggiare", "zaino in spalla", "escursione", "avventura",
        # Dutch (nl)
        "reis", "reizen", "wandelen", "rugzak", "avontuur",
        # Russian (ru)
        "путешествие", "поход", "рюкзак", "приключение", "восхождение",
        # Polish (pl)
        "podróż", "podróżować", "wędrówka", "plecak", "przygoda",
        # Turkish (tr)
        "seyahat", "gezi", "yürüyüş", "macera", "tırmanış",
        # Japanese (ja)
        "旅行", "ハイキング", "冒険", "バックパック", "登山",
        # Korean (ko)
        "여행", "하이킹", "모험", "배낭여행", "등산",
        # Chinese (zh)
        "旅行", "徒步", "冒险", "背包旅行", "登山",
        # Arabic (ar)
        "سفر", "رحلة", "مغامرة", "تسلق", "حقيبة ظهر",
        # Hindi (hi)
        "यात्रा", "सफर", "पर्वतारोहण", "रोमांच", "ट्रेकिंग",
        # Haitian Creole (ht)
        "vwayaj", "vwayaje", "aventire", "randonnen", "monte",
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
        # Spanish (es)
        "examen", "universidad", "diploma", "estudiar", "carrera universitaria",
        # Portuguese (pt)
        "exame", "universidade", "diploma", "estudar", "faculdade",
        # German (de)
        "prüfung", "universität", "diplom", "studieren", "abschluss",
        # Italian (it)
        "esame", "università", "diploma", "studiare", "laurea",
        # Dutch (nl)
        "examen", "universiteit", "diploma", "studeren", "afstuderen",
        # Russian (ru)
        "экзамен", "университет", "диплом", "учиться", "образование",
        # Polish (pl)
        "egzamin", "uniwersytet", "dyplom", "studiować", "wykształcenie",
        # Turkish (tr)
        "sınav", "üniversite", "diploma", "okumak", "eğitim",
        # Japanese (ja)
        "試験", "大学", "卒業", "勉強", "資格",
        # Korean (ko)
        "시험", "대학교", "졸업", "공부", "자격증",
        # Chinese (zh)
        "考试", "大学", "毕业", "学习", "文凭",
        # Arabic (ar)
        "امتحان", "جامعة", "شهادة", "دراسة", "تعليم",
        # Hindi (hi)
        "परीक्षा", "विश्वविद्यालय", "डिग्री", "पढ़ाई", "शिक्षा",
        # Haitian Creole (ht)
        "egzamen", "inivèsite", "diplòm", "etidye", "edikasyon",
    ],
    "home_renovation": [
        "rénover",
        "renovation",
        "maison",
        "house",
        "appartement",
        "apartment",
        "peinture",
        "paint",
        "cuisine",
        "kitchen",
        "salle de bain",
        "bathroom",
        "décoration",
        "decoration",
        "meubles",
        "furniture",
        "aménagement",
        "jardin",
        "garden",
        "terrasse",
        # Spanish (es)
        "renovar", "casa", "cocina", "baño", "decoración",
        # Portuguese (pt)
        "reformar", "casa", "cozinha", "banheiro", "decoração",
        # German (de)
        "renovieren", "haus", "küche", "badezimmer", "dekoration",
        # Italian (it)
        "ristrutturare", "casa", "cucina", "bagno", "arredamento",
        # Dutch (nl)
        "renoveren", "huis", "keuken", "badkamer", "decoratie",
        # Russian (ru)
        "ремонт", "дом", "кухня", "ванная", "декор",
        # Polish (pl)
        "remont", "dom", "kuchnia", "łazienka", "dekoracja",
        # Turkish (tr)
        "tadilat", "ev", "mutfak", "banyo", "dekorasyon",
        # Japanese (ja)
        "リフォーム", "家", "キッチン", "バスルーム", "インテリア",
        # Korean (ko)
        "리모델링", "집", "주방", "욕실", "인테리어",
        # Chinese (zh)
        "装修", "房子", "厨房", "浴室", "装饰",
        # Arabic (ar)
        "تجديد", "منزل", "مطبخ", "حمام", "ديكور",
        # Hindi (hi)
        "नवीनीकरण", "घर", "रसोई", "बाथरूम", "सजावट",
        # Haitian Creole (ht)
        "renovasyon", "kay", "kizin", "twalèt", "dekorasyon",
    ],
    "diy": [
        "bricolage",
        "diy",
        "bois",
        "wood",
        "menuiserie",
        "woodworking",
        "couture",
        "sewing",
        "tricot",
        "knitting",
        "crochet",
        "bijoux",
        "jewelry",
        "céramique",
        "ceramic",
        "savon",
        "soap",
        "bougie",
        "candle",
    ],
    "parenting": [
        "enfant",
        "child",
        "bébé",
        "baby",
        "parent",
        "maman",
        "papa",
        "éducation enfant",
        "grossesse",
        "pregnancy",
        "naissance",
        "birth",
        "allaitement",
        "famille",
        "family planning",
        # Spanish (es)
        "niño", "bebé", "padre", "madre", "crianza",
        # Portuguese (pt)
        "criança", "bebê", "pai", "mãe", "paternidade",
        # German (de)
        "kind", "eltern", "erziehung", "schwangerschaft", "geburt",
        # Italian (it)
        "bambino", "genitore", "educazione", "gravidanza", "nascita",
        # Dutch (nl)
        "kind", "ouder", "opvoeding", "zwangerschap", "geboorte",
        # Russian (ru)
        "ребёнок", "родитель", "воспитание", "беременность", "рождение",
        # Polish (pl)
        "dziecko", "rodzic", "wychowanie", "ciąża", "narodziny",
        # Turkish (tr)
        "çocuk", "ebeveyn", "hamilelik", "doğum", "anne",
        # Japanese (ja)
        "子供", "育児", "親", "妊娠", "出産",
        # Korean (ko)
        "아이", "육아", "부모", "임신", "출산",
        # Chinese (zh)
        "孩子", "育儿", "父母", "怀孕", "出生",
        # Arabic (ar)
        "طفل", "والد", "تربية", "حمل", "ولادة",
        # Hindi (hi)
        "बच्चा", "माता-पिता", "पालन-पोषण", "गर्भावस्था", "जन्म",
        # Haitian Creole (ht)
        "timoun", "paran", "edikasyon timoun", "gwosès", "nesans",
    ],
    "pets": [
        "chien",
        "dog",
        "chat",
        "cat",
        "animal",
        "pet",
        "aquarium",
        "poisson",
        "fish",
        "oiseau",
        "bird",
        "cheval",
        "horse",
        "dressage",
        "training",
        "adoption",
        "refuge",
        "élevage",
    ],
    "gardening": [
        "jardinage",
        "jardin",
        "potager",
        "vegetable garden",
        "planter",
        "planting",
        "graines",
        "seeds",
        "fleurs",
        "flowers",
        "arbre",
        "tree",
        "compost",
        "permaculture",
        "serre",
        "greenhouse",
    ],
    "real_estate": [
        "acheter maison",
        "buy house",
        "immobilier",
        "real estate",
        "appartement",
        "hypothèque",
        "mortgage",
        "propriétaire",
        "homeowner",
        "investissement locatif",
        "rental investment",
        "loyer",
        "rent",
        "copropriété",
        "condo",
        # Spanish (es)
        "comprar casa", "inmobiliario", "hipoteca", "propiedad", "alquiler",
        # Portuguese (pt)
        "comprar casa", "imobiliário", "hipoteca", "propriedade", "aluguel",
        # German (de)
        "haus kaufen", "immobilien", "hypothek", "eigentum", "miete",
        # Italian (it)
        "comprare casa", "immobiliare", "mutuo", "proprietà", "affitto",
        # Dutch (nl)
        "huis kopen", "vastgoed", "hypotheek", "eigendom", "huur",
        # Russian (ru)
        "купить дом", "недвижимость", "ипотека", "собственность", "аренда",
        # Polish (pl)
        "kupić dom", "nieruchomości", "hipoteka", "własność", "wynajem",
        # Turkish (tr)
        "ev almak", "emlak", "ipotek", "mülk", "kira",
        # Japanese (ja)
        "家を買う", "不動産", "住宅ローン", "物件", "賃貸",
        # Korean (ko)
        "집 사기", "부동산", "주택담보대출", "재산", "임대",
        # Chinese (zh)
        "买房", "房地产", "按揭", "房产", "租金",
        # Arabic (ar)
        "شراء منزل", "عقارات", "رهن عقاري", "ملكية", "إيجار",
        # Hindi (hi)
        "घर खरीदना", "रियल एस्टेट", "गृह ऋण", "संपत्ति", "किराया",
        # Haitian Creole (ht)
        "achte kay", "imobilye", "ipotèk", "pwopriyete", "lwaye",
    ],
    "retirement": [
        "retraite",
        "retirement",
        "pension",
        "épargne retraite",
        "401k",
        "rrsp",
        "reer",
        "planification retraite",
        "retirement planning",
        "liberté financière",
        "financial freedom",
        "vivre de ses rentes",
    ],
    "volunteer": [
        "bénévolat",
        "volunteer",
        "humanitaire",
        "humanitarian",
        "ong",
        "ngo",
        "association",
        "charity",
        "don",
        "donation",
        "communauté",
        "community service",
        "aide",
        "help",
        "impact social",
    ],
    "sobriety": [
        "sobriété",
        "sobriety",
        "arrêter de fumer",
        "quit smoking",
        "alcool",
        "alcohol",
        "addiction",
        "dépendance",
        "dependency",
        "rétablissement",
        "recovery",
        "sevrage",
        "detox",
        "tabac",
        "tobacco",
        "drogue",
        # Spanish (es)
        "dejar de fumar", "sobriedad", "adicción", "alcohol", "rehabilitación",
        # Portuguese (pt)
        "parar de fumar", "sobriedade", "vício", "álcool", "reabilitação",
        # German (de)
        "aufhören zu rauchen", "nüchternheit", "sucht", "alkohol", "entzug",
        # Italian (it)
        "smettere di fumare", "sobrietà", "dipendenza", "alcol", "riabilitazione",
        # Dutch (nl)
        "stoppen met roken", "nuchterheid", "verslaving", "alcohol", "afkicken",
        # Russian (ru)
        "бросить курить", "трезвость", "зависимость", "алкоголь", "реабилитация",
        # Polish (pl)
        "rzucić palenie", "trzeźwość", "uzależnienie", "alkohol", "odwyk",
        # Turkish (tr)
        "sigarayı bırakmak", "bağımlılık", "alkol", "ayıklık", "rehabilitasyon",
        # Japanese (ja)
        "禁煙", "断酒", "依存症", "アルコール", "リハビリ",
        # Korean (ko)
        "금연", "금주", "중독", "알코올", "재활",
        # Chinese (zh)
        "戒烟", "戒酒", "成瘾", "酒精", "康复",
        # Arabic (ar)
        "إقلاع عن التدخين", "إدمان", "كحول", "تعافي", "علاج إدمان",
        # Hindi (hi)
        "धूम्रपान छोड़ना", "नशामुक्ति", "लत", "शराब", "पुनर्वास",
        # Haitian Creole (ht)
        "sispann fimen", "sobryete", "depandans", "alkòl", "reyabilitasyon",
    ],
    "environmental": [
        "écologie",
        "ecology",
        "environnement",
        "environment",
        "zéro déchet",
        "zero waste",
        "recyclage",
        "recycling",
        "durable",
        "sustainable",
        "bio",
        "organic",
        "végan",
        "vegan",
        "végétarien",
        "vegetarian",
        "climat",
        "climate",
        "empreinte carbone",
        "carbon footprint",
        # Spanish (es)
        "ecología", "medio ambiente", "reciclaje", "sostenible", "cero residuos",
        # Portuguese (pt)
        "ecologia", "meio ambiente", "reciclagem", "sustentável", "lixo zero",
        # German (de)
        "ökologie", "umwelt", "recycling", "nachhaltig", "null abfall",
        # Italian (it)
        "ecologia", "ambiente", "riciclo", "sostenibile", "rifiuti zero",
        # Dutch (nl)
        "ecologie", "milieu", "recycling", "duurzaam", "afvalvrij",
        # Russian (ru)
        "экология", "окружающая среда", "переработка", "устойчивый", "ноль отходов",
        # Polish (pl)
        "ekologia", "środowisko", "recykling", "zrównoważony", "zero waste",
        # Turkish (tr)
        "ekoloji", "çevre", "geri dönüşüm", "sürdürülebilir", "sıfır atık",
        # Japanese (ja)
        "エコロジー", "環境", "リサイクル", "持続可能", "ゼロウェイスト",
        # Korean (ko)
        "생태", "환경", "재활용", "지속가능", "제로웨이스트",
        # Chinese (zh)
        "生态", "环境", "回收", "可持续", "零废弃",
        # Arabic (ar)
        "بيئة", "إعادة تدوير", "استدامة", "صفر نفايات", "مناخ",
        # Hindi (hi)
        "पारिस्थितिकी", "पर्यावरण", "पुनर्चक्रण", "टिकाऊ", "शून्य अपशिष्ट",
        # Haitian Creole (ht)
        "ekoloji", "anviwònman", "resiklaj", "dirab", "zewo dechè",
    ],
    "endurance": [
        "marathon",
        "semi-marathon",
        "half marathon",
        "10k",
        "5k",
        "trail",
        "ultra trail",
        "triathlon",
        "ironman",
        "course à pied",
        "running race",
        "endurance",
        "chrono",
        "temps",
        "pace",
    ],
    "martial_arts": [
        "arts martiaux",
        "martial arts",
        "boxe",
        "boxing",
        "mma",
        "karate",
        "judo",
        "taekwondo",
        "jiu-jitsu",
        "bjj",
        "muay thai",
        "kickboxing",
        "krav maga",
        "kung fu",
        "self-defense",
        "autodéfense",
        "ceinture",
        "belt",
    ],
    "dance": [
        "danse",
        "dance",
        "salsa",
        "bachata",
        "tango",
        "hip hop",
        "ballet",
        "contemporain",
        "contemporary",
        "breakdance",
        "valse",
        "waltz",
        "chorégraphie",
        "choreography",
        "danseur",
        "dancer",
    ],
    "outdoor": [
        "survie",
        "survival",
        "bushcraft",
        "camping",
        "bivouac",
        "montagne",
        "mountain",
        "escalade",
        "climbing",
        "alpinisme",
        "mountaineering",
        "kayak",
        "canoe",
        "voile",
        "sailing",
        "plongée",
        "scuba",
    ],
    "body_transformation": [
        "transformation",
        "avant après",
        "before after",
        "body",
        "corps",
        "musculation",
        "bodybuilding",
        "prise de masse",
        "bulk",
        "sèche",
        "cut",
        "définition",
        "physique",
        "shape",
        "forme",
        # Spanish (es)
        "transformación corporal", "musculación", "masa muscular", "definición", "cuerpo",
        # Portuguese (pt)
        "transformação corporal", "musculação", "massa muscular", "definição", "corpo",
        # German (de)
        "körpertransformation", "muskelaufbau", "muskelmasse", "definition", "körper",
        # Italian (it)
        "trasformazione corporea", "muscolazione", "massa muscolare", "definizione", "corpo",
        # Dutch (nl)
        "lichaamstransformatie", "spieropbouw", "spiermassa", "definitie", "lichaam",
        # Russian (ru)
        "трансформация тела", "бодибилдинг", "мышечная масса", "рельеф", "тело",
        # Polish (pl)
        "transformacja ciała", "budowanie mięśni", "masa mięśniowa", "rzeźba", "ciało",
        # Turkish (tr)
        "vücut dönüşümü", "kas yapma", "kas kütlesi", "tanımlı vücut", "vücut",
        # Japanese (ja)
        "ボディメイク", "筋肉", "肉体改造", "バルクアップ", "体づくり",
        # Korean (ko)
        "바디프로필", "근육", "벌크업", "몸만들기", "체형변화",
        # Chinese (zh)
        "身体改造", "肌肉", "增肌", "减脂", "塑形",
        # Arabic (ar)
        "تحول جسدي", "بناء عضلات", "كتلة عضلية", "تنشيف", "جسم",
        # Hindi (hi)
        "शरीर परिवर्तन", "बॉडीबिल्डिंग", "मांसपेशियां", "कटिंग", "शरीर",
        # Haitian Creole (ht)
        "transfòmasyon kò", "misk", "kò", "fòm", "egzèsis fòs",
    ],
    "mental_health": [
        "santé mentale",
        "mental health",
        "anxiété",
        "anxiety",
        "dépression",
        "depression",
        "thérapie",
        "therapy",
        "psychologue",
        "burn-out",
        "burnout",
        "stress",
        "panique",
        "panic",
        "phobia",
        "phobie",
        "trauma",
        "estime de soi",
        "self-esteem",
        # Spanish (es)
        "salud mental", "ansiedad", "depresión", "terapia", "psicólogo",
        # Portuguese (pt)
        "saúde mental", "ansiedade", "depressão", "terapia", "psicólogo",
        # German (de)
        "psychische gesundheit", "angst", "depression", "therapie", "psychologe",
        # Italian (it)
        "salute mentale", "ansia", "depressione", "terapia", "psicologo",
        # Dutch (nl)
        "geestelijke gezondheid", "angst", "depressie", "therapie", "psycholoog",
        # Russian (ru)
        "психическое здоровье", "тревога", "депрессия", "терапия", "психолог",
        # Polish (pl)
        "zdrowie psychiczne", "lęk", "depresja", "terapia", "psycholog",
        # Turkish (tr)
        "ruh sağlığı", "kaygı", "depresyon", "terapi", "psikolog",
        # Japanese (ja)
        "メンタルヘルス", "不安", "うつ病", "セラピー", "心理",
        # Korean (ko)
        "정신건강", "불안", "우울증", "치료", "심리",
        # Chinese (zh)
        "心理健康", "焦虑", "抑郁", "治疗", "心理医生",
        # Arabic (ar)
        "صحة نفسية", "قلق", "اكتئاب", "علاج نفسي", "طبيب نفسي",
        # Hindi (hi)
        "मानसिक स्वास्थ्य", "चिंता", "अवसाद", "थेरेपी", "मनोवैज्ञानिक",
        # Haitian Creole (ht)
        "sante mantal", "enkyetid", "depresyon", "terapi", "sikolojis",
    ],
    "sleep": [
        "sommeil",
        "sleep",
        "dormir",
        "insomnie",
        "insomnia",
        "réveil",
        "wake up",
        "se lever tôt",
        "early riser",
        "chronotype",
        "rythme",
        "fatigue",
        "énergie",
        "energy",
        "sieste",
        "nap",
        "récupération",
        # Spanish (es)
        "sueño", "dormir", "insomnio", "despertarse", "descanso",
        # Portuguese (pt)
        "sono", "dormir", "insônia", "acordar", "descanso",
        # German (de)
        "schlaf", "schlafen", "schlaflosigkeit", "aufwachen", "erholung",
        # Italian (it)
        "sonno", "dormire", "insonnia", "svegliarsi", "riposo",
        # Dutch (nl)
        "slaap", "slapen", "slapeloosheid", "wakker worden", "rust",
        # Russian (ru)
        "сон", "спать", "бессонница", "просыпаться", "отдых",
        # Polish (pl)
        "sen", "spać", "bezsenność", "budzić się", "odpoczynek",
        # Turkish (tr)
        "uyku", "uyumak", "uykusuzluk", "uyanmak", "dinlenme",
        # Japanese (ja)
        "睡眠", "寝る", "不眠症", "早起き", "休息",
        # Korean (ko)
        "수면", "잠자기", "불면증", "기상", "휴식",
        # Chinese (zh)
        "睡眠", "睡觉", "失眠", "早起", "休息",
        # Arabic (ar)
        "نوم", "أرق", "استيقاظ", "راحة", "طاقة",
        # Hindi (hi)
        "नींद", "सोना", "अनिद्रा", "जल्दी उठना", "आराम",
        # Haitian Creole (ht)
        "dòmi", "somèy", "ensomni", "leve bonè", "repo",
    ],
    "aging": [
        "vieillir",
        "aging",
        "senior",
        "retraité",
        "retired",
        "longévité",
        "longevity",
        "mémoire",
        "memory",
        "cognitif",
        "cognitive",
        "mobilité",
        "mobility",
        "anti-âge",
        "anti-aging",
    ],
    "weight_management": [
        "poids",
        "weight",
        "maigrir",
        "perdre",
        "lose",
        "grossir",
        "gain",
        "imc",
        "bmi",
        "calories",
        "régime",
        "diet",
        "mincir",
        "slim",
        "obésité",
        "obesity",
        # Spanish (es)
        "peso", "adelgazar", "engordar", "calorías", "dieta",
        # Portuguese (pt)
        "peso", "emagrecer", "engordar", "calorias", "dieta",
        # German (de)
        "gewicht", "abnehmen", "zunehmen", "kalorien", "diät",
        # Italian (it)
        "peso", "dimagrire", "ingrassare", "calorie", "dieta",
        # Dutch (nl)
        "gewicht", "afvallen", "aankomen", "calorieën", "dieet",
        # Russian (ru)
        "вес", "похудеть", "набрать вес", "калории", "диета",
        # Polish (pl)
        "waga", "schudnąć", "przytyć", "kalorie", "dieta",
        # Turkish (tr)
        "kilo", "zayıflamak", "kilo almak", "kalori", "diyet",
        # Japanese (ja)
        "体重", "痩せる", "太る", "カロリー", "ダイエット",
        # Korean (ko)
        "체중", "살빼기", "살찌기", "칼로리", "다이어트",
        # Chinese (zh)
        "体重", "减肥", "增重", "卡路里", "节食",
        # Arabic (ar)
        "وزن", "تخسيس", "زيادة الوزن", "سعرات", "حمية",
        # Hindi (hi)
        "वजन", "वजन घटाना", "वजन बढ़ाना", "कैलोरी", "डाइट",
        # Haitian Creole (ht)
        "pwa", "pèdi pwa", "pran pwa", "kalori", "rejim",
    ],
    "fertility": [
        "enceinte",
        "pregnant",
        "grossesse",
        "pregnancy",
        "bébé",
        "baby",
        "fertilité",
        "fertility",
        "fiv",
        "ivf",
        "conception",
        "accouchement",
        "birth",
        "maternité",
        "maternity",
        "paternité",
        "paternity",
    ],
    "music_production": [
        "production musicale",
        "beatmaking",
        "beat",
        "ableton",
        "fl studio",
        "logic pro",
        "mixing",
        "mastering",
        "rappeur",
        "rapper",
        "chanteur",
        "singer",
        "album",
        "single",
        "spotify",
    ],
    "writing": [
        "écrire un livre",
        "write a book",
        "roman",
        "novel",
        "poésie",
        "poetry",
        "scénario",
        "screenplay",
        "blog",
        "blogging",
        "auteur",
        "author",
        "publier",
        "publish",
        "écriture créative",
        "creative writing",
        "manuscrit",
        "manuscript",
    ],
    "fashion": [
        "mode",
        "fashion",
        "style",
        "v\u00eatement",
        "clothing",
        "garde-robe",
        "wardrobe",
        "couture",
        "design",
        "tendance",
        "trend",
        "lookbook",
        "shopping",
        "élégance",
    ],
    "public_speaking": [
        "présentation",
        "presentation",
        "discours",
        "speech",
        "conférence",
        "conference",
        "ted talk",
        "pitch",
        "oral",
        "prise de parole",
        "éloquence",
        "eloquence",
        "débat",
        "debate",
        "négociation",
        "negotiation",
    ],
    "content_creation": [
        "influenceur",
        "influencer",
        "instagram",
        "tiktok",
        "youtube",
        "podcast",
        "blog",
        "newsletter",
        "contenu",
        "content creator",
        "audience",
        "followers",
        "abonnés",
        "monétisation",
        "monetization",
    ],
    "minimalism": [
        "minimalisme",
        "minimalism",
        "désencombrer",
        "declutter",
        "simplifier",
        "simplify",
        "ranger",
        "organize",
        "trier",
        "sort",
        "marie kondo",
        "essentiel",
        "essential",
        "sobriété",
    ],
    "digital_detox": [
        "détox digitale",
        "digital detox",
        "écran",
        "screen time",
        "téléphone",
        "phone addiction",
        "réseaux sociaux",
        "social media detox",
        "déconnexion",
        "disconnect",
        "nomophobie",
        "doomscrolling",
    ],
    "organization": [
        "organisation",
        "organizing",
        "ranger",
        "tidy",
        "ménage",
        "cleaning",
        "productivité maison",
        "home management",
        "planning",
        "planification",
        "agenda",
        "planner",
        "bullet journal",
    ],
    "emigration": [
        "émigrer",
        "emigrate",
        "immigrer",
        "immigrate",
        "expatrier",
        "expat",
        "visa",
        "permis de travail",
        "work permit",
        "résidence",
        "residence",
        "déménager",
        "move abroad",
        "pays",
        "country",
        "s\'installer",
    ],
    "event_planning": [
        "mariage",
        "wedding",
        "événement",
        "event",
        "fête",
        "party",
        "anniversaire",
        "birthday",
        "organisateur",
        "organizer",
        "réception",
        "banquet",
        "cérémonie",
        "ceremony",
        "gala",
    ],
    "social_media": [
        "instagram growth",
        "tiktok growth",
        "followers",
        "abonnés",
        "réseaux sociaux",
        "social media growth",
        "viralité",
        "viral",
        "engagement",
        "algorithme",
        "algorithm",
        "personal branding",
        "marque personnelle",
    ],
    "podcast": [
        "podcast",
        "épisode",
        "episode",
        "micro",
        "microphone",
        "enregistrement",
        "recording",
        "audio",
        "spotify podcast",
        "apple podcast",
        "interview",
        "invité",
        "guest",
    ],
    "app_dev": [
        "application",
        "app development",
        "développer une app",
        "build an app",
        "mobile app",
        "ios",
        "android",
        "react native",
        "flutter",
        "swift",
        "kotlin",
        "app store",
        "play store",
    ],
    "book": [
        "livre",
        "book",
        "écrire un livre",
        "write a book",
        "publier",
        "publish",
        "manuscrit",
        "manuscript",
        "éditeur",
        "editor",
        "autoédition",
        "self-publishing",
        "kindle",
        "amazon author",
    ],
    "online_course": [
        "cours en ligne",
        "online course",
        "formation en ligne",
        "e-learning",
        "udemy",
        "teachable",
        "masterclass",
        "webinaire",
        "webinar",
        "tutoriel",
        "tutorial",
        "certification",
        "enseigner en ligne",
    ],
    "research": [
        "thèse",
        "thesis",
        "mémoire",
        "dissertation",
        "recherche",
        "research",
        "doctorat",
        "phd",
        "publication",
        "article scientifique",
        "scientific paper",
        "laboratoire",
        "lab",
        "professeur",
        "professor",
    ],
    "competitive_exam": [
        "concours",
        "competitive exam",
        "prépa",
        "preparation",
        "agrégation",
        "capes",
        "fonction publique",
        "civil service",
        "médecine",
        "medicine entrance",
        "barreau",
        "bar exam",
        "admission",
    ],
    "data_science": [
        "data science",
        "machine learning",
        "deep learning",
        "intelligence artificielle",
        "ai",
        "python data",
        "statistiques",
        "statistics",
        "tableau",
        "power bi",
        "analyse de données",
        "data analysis",
        "kaggle",
        "tensorflow",
        "pytorch",
    ],
    "cybersecurity": [
        "cybersécurité",
        "cybersecurity",
        "hacking",
        "ethical hacking",
        "pentest",
        "sécurité informatique",
        "infosec",
        "ctf",
        "bug bounty",
        "oscp",
        "ceh",
        "firewall",
        "malware",
        "forensic",
    ],
    "teaching": [
        "enseigner",
        "teach",
        "tuteur",
        "tutor",
        "mentor",
        "formation",
        "training course",
        "atelier",
        "workshop",
        "cours",
        "lesson",
        "pédagogie",
        "pedagogy",
        "formateur",
        "trainer",
        "professeur",
        "enseignant",
    ],
    "automotive": [
        "voiture",
        "car",
        "moto",
        "motorcycle",
        "mécanique",
        "mechanic",
        "conduire",
        "driving",
        "permis de conduire",
        "restauration",
        "restoration",
        "tuning",
        "moteur",
        "engine",
    ],
    "gaming": [
        "gaming",
        "jeu vidéo",
        "video game",
        "esport",
        "rang",
        "rank",
        "compétitif",
        "competitive",
        "twitch",
        "streaming",
        "speedrun",
        "tournament",
        "tournoi",
    ],
    "culinary": [
        "gastronomie",
        "gastronomy",
        "chef",
        "pâtisserie",
        "pastry",
        "boulangerie",
        "bakery",
        "fermentation",
        "sommelier",
        "vin",
        "wine",
        "restaurant",
        "food truck",
        "traiteur",
        "catering",
    ],
    "photography": [
        "photo",
        "photographie",
        "photography",
        "vidéo",
        "video",
        "film",
        "cinéma",
        "camera",
        "lightroom",
        "photoshop",
        "youtube",
        "filmmaker",
        "drone",
        "montage",
        "editing",
    ],
    "spirituality": [
        "méditation",
        "meditation",
        "spirituel",
        "spiritual",
        "yoga",
        "pleine conscience",
        "mindfulness",
        "zen",
        "reiki",
        "chakra",
        "prière",
        "prayer",
        "bien-être",
        "wellness",
        "détox",
        "detox",
        "respiration",
        "breathing",
        # Spanish (es)
        "meditación", "espiritualidad", "bienestar", "oración", "respiración",
        # Portuguese (pt)
        "meditação", "espiritualidade", "bem-estar", "oração", "respiração",
        # German (de)
        "meditation", "spiritualität", "wohlbefinden", "gebet", "atmung",
        # Italian (it)
        "meditazione", "spiritualità", "benessere", "preghiera", "respirazione",
        # Dutch (nl)
        "meditatie", "spiritualiteit", "welzijn", "gebed", "ademhaling",
        # Russian (ru)
        "медитация", "духовность", "благополучие", "молитва", "дыхание",
        # Polish (pl)
        "medytacja", "duchowość", "dobrostan", "modlitwa", "oddychanie",
        # Turkish (tr)
        "meditasyon", "maneviyat", "iyi oluş", "dua", "nefes",
        # Japanese (ja)
        "瞑想", "スピリチュアル", "ウェルネス", "祈り", "呼吸法",
        # Korean (ko)
        "명상", "영성", "웰빙", "기도", "호흡법",
        # Chinese (zh)
        "冥想", "灵性", "身心健康", "祈祷", "呼吸法",
        # Arabic (ar)
        "تأمل", "روحانية", "رفاهية", "صلاة", "تنفس",
        # Hindi (hi)
        "ध्यान", "आध्यात्मिकता", "कल्याण", "प्रार्थना", "श्वास",
        # Haitian Creole (ht)
        "meditasyon", "espirityalite", "byennèt", "lapriyè", "respirasyon",
    ],
    "relocation": [
        "déménager",
        "move",
        "déménagement",
        "moving",
        "nouvelle ville",
        "new city",
        "emménager",
        "settle",
        "maison neuve",
        "new home",
        "changement de ville",
    ],
    "wedding": [
        "mariage",
        "wedding",
        "fiançailles",
        "engagement",
        "noces",
        "cérémonie",
        "ceremony",
        "réception",
        "venue",
        "robe de mariée",
        "wedding dress",
        "traiteur",
        "caterer",
        "lune de miel",
        "honeymoon",
    ],
    "car_purchase": [
        "acheter voiture",
        "buy car",
        "nouvelle voiture",
        "new car",
        "véhicule",
        "vehicle",
        "occasion",
        "used car",
        "financement",
        "financing",
        "leasing",
        "assurance auto",
        "car insurance",
    ],
    "immersion": [
        "immersion",
        "séjour linguistique",
        "language stay",
        "année à l'étranger",
        "year abroad",
        "erasmus",
        "exchange",
        "au pair",
        "pvt",
        "working holiday",
        "vivre à l'étranger",
        "live abroad",
    ],
    "digital_nomad": [
        "nomade digital",
        "digital nomad",
        "télétravail voyager",
        "remote work travel",
        "travailler en voyageant",
        "work and travel",
        "coworking",
        "van life",
        "backpacker travailleur",
    ],
    "driving": [
        "permis",
        "permis de conduire",
        "driving license",
        "auto-école",
        "driving school",
        "code de la route",
        "highway code",
        "conduite",
        "driving",
        "examen de conduite",
        "driving test",
        "leçon de conduite",
    ],
    "extreme_sports": [
        "parachutisme",
        "skydiving",
        "bungee",
        "saut à l'élastique",
        "parapente",
        "paragliding",
        "base jump",
        "wingsuit",
        "escalade extrême",
        "canyoning",
        "rafting",
        "sports extrêmes",
        "extreme sports",
        "adrénaline",
    ],
    "retirement_hobby": [
        "loisir retraite",
        "retirement hobby",
        "activité senior",
        "senior activity",
        "club senior",
        "activité après retraite",
        "hobby retiree",
        "temps libre",
        "free time retirement",
    ],
    "competition": [
        "compétition",
        "competition",
        "championnat",
        "championship",
        "concours",
        "contest",
        "médaille",
        "medal",
        "performance",
        "record",
        "podium",
        "qualifications",
        "sélection",
    ],
    "life_transition": [
        "divorce",
        "séparation",
        "separation",
        "deuil",
        "grief",
        "licenciement",
        "layoff",
        "reconversion",
        "career change",
        "recommencer",
        "start over",
        "nouvelle vie",
        "new life",
        "changement de vie",
        "life change",
        "transition",
    ],
    "dating": [
        "rencontre",
        "dating",
        "séduction",
        "seduction",
        "tinder",
        "bumble",
        "amour",
        "love",
        "célibataire",
        "single",
        "partenaire",
        "partner",
        "relation amoureuse",
        "trouver l'amour",
        "find love",
    ],
    "confidence": [
        "confiance en soi",
        "self-confidence",
        "estime de soi",
        "self-esteem",
        "timidité",
        "shyness",
        "introversion",
        "assurance",
        "assertivité",
        "assertiveness",
        "s'affirmer",
        "syndrome imposteur",
        "imposter syndrome",
    ],
    "leadership": [
        "leadership",
        "leader",
        "manager",
        "management",
        "diriger",
        "lead",
        "équipe",
        "team",
        "gestion",
        "patron",
        "boss",
        "chef d'équipe",
        "team lead",
        "directeur",
        "director",
    ],
    "networking": [
        "réseautage",
        "networking",
        "contact",
        "réseau professionnel",
        "professional network",
        "linkedin",
        "connexion",
        "connection",
        "mentorat",
        "mentorship",
        "parrainage",
        "sponsorship",
    ],
    "communication": [
        "communication",
        "s'exprimer",
        "express",
        "parler",
        "speak",
        "écouter",
        "listen",
        "persuader",
        "persuade",
        "convaincre",
        "convince",
        "argumenter",
        "articulate",
        "dialogue",
        "conversation",
    ],
    "startup": [
        "startup",
        "lancer",
        "launch",
        "idée",
        "idea",
        "innovation",
        "app",
        "saas",
        "plateforme",
        "platform",
        "levée de fonds",
        "fundraising",
        "investisseur",
        "investor",
        "incubateur",
        "accelerator",
        "pitch",
        # Spanish (es)
        "emprendimiento", "lanzar", "idea de negocio", "inversión", "innovación",
        # Portuguese (pt)
        "empreendedorismo", "lançar", "ideia de negócio", "investimento", "inovação",
        # German (de)
        "gründung", "starten", "geschäftsidee", "investition", "innovation",
        # Italian (it)
        "imprenditoria", "lanciare", "idea imprenditoriale", "investimento", "innovazione",
        # Dutch (nl)
        "ondernemerschap", "lanceren", "bedrijfsidee", "investering", "innovatie",
        # Russian (ru)
        "стартап", "запустить", "бизнес-идея", "инвестиция", "инновация",
        # Polish (pl)
        "startup", "uruchomić", "pomysł na biznes", "inwestycja", "innowacja",
        # Turkish (tr)
        "girişim", "başlatmak", "iş fikri", "yatırım", "inovasyon",
        # Japanese (ja)
        "スタートアップ", "起業する", "ビジネスアイデア", "投資", "イノベーション",
        # Korean (ko)
        "스타트업", "창업하기", "사업 아이디어", "투자", "혁신",
        # Chinese (zh)
        "创业公司", "启动", "商业想法", "投资", "创新",
        # Arabic (ar)
        "شركة ناشئة", "إطلاق", "فكرة مشروع", "استثمار", "ابتكار",
        # Hindi (hi)
        "स्टार्टअप", "शुरू करना", "व्यापार विचार", "निवेश", "नवाचार",
        # Haitian Creole (ht)
        "antrepriz", "lanse", "ide biznis", "envestisman", "inovasyon",
    ],
    "freelance": [
        "freelance",
        "indépendant",
        "independent",
        "auto-entrepreneur",
        "micro-entreprise",
        "consultant",
        "prestataire",
        "missions",
        "clients",
        "portfolio",
        "tarif",
        "rate",
        "facturation",
    ],
    "side_hustle": [
        "side hustle",
        "revenu complémentaire",
        "extra income",
        "à côté",
        "side project",
        "revenus passifs",
        "passive income",
        "dropshipping",
        "e-commerce",
        "vente en ligne",
        "online selling",
        "fiverr",
        "upwork",
    ],
    "ecommerce": [
        "e-commerce",
        "ecommerce",
        "boutique en ligne",
        "online store",
        "shopify",
        "etsy",
        "amazon",
        "vendre",
        "sell online",
        "produit",
        "product",
        "livraison",
        "shipping",
        "stock",
        "inventory",
    ],
    "nonprofit": [
        "association",
        "créer une association",
        "ong",
        "ngo",
        "fondation",
        "foundation",
        "cause",
        "mission",
        "subvention",
        "grant",
        "collecte de fonds",
        "fundraising",
        "social enterprise",
    ],
    "prepping": [
        "préparation",
        "preparedness",
        "urgence",
        "emergency",
        "survivalisme",
        "prepping",
        "trousse",
        "kit",
        "réserves",
        "stockage",
        "storage",
        "catastrophe",
        "disaster",
        "autonomie",
        "self-sufficiency",
    ],
    "instrument": [
        "guitare",
        "guitar",
        "piano",
        "violon",
        "violin",
        "batterie",
        "drums",
        "basse",
        "bass",
        "ukulélé",
        "ukulele",
        "saxophone",
        "flûte",
        "flute",
        "trompette",
        "trumpet",
        "instrument de musique",
    ],
    "visual_art": [
        "peinture",
        "painting",
        "dessin",
        "drawing",
        "aquarelle",
        "watercolor",
        "huile",
        "oil painting",
        "acrylique",
        "acrylic",
        "illustration",
        "sketch",
        "croquis",
        "portrait",
        "paysage",
        "landscape",
        "nature morte",
        "still life",
    ],
    "collecting": [
        "collection",
        "collecting",
        "collectionner",
        "collector",
        "carte",
        "cards",
        "timbre",
        "stamp",
        "monnaie",
        "coin",
        "vintage",
        "antique",
        "figurine",
        "vinyle",
        "vinyl",
        "sneakers",
        "lego",
    ],
    "urban_farming": [
        "agriculture urbaine",
        "urban farming",
        "balcon",
        "balcony garden",
        "potager urbain",
        "city garden",
        "hydroponie",
        "hydroponics",
        "aquaponie",
        "microgreens",
        "herbes",
        "herbs",
        "tomates",
        "tomatoes",
    ],
    "investing": [
        "investir",
        "invest",
        "bourse",
        "stock market",
        "actions",
        "stocks",
        "etf",
        "obligations",
        "bonds",
        "dividendes",
        "dividends",
        "portefeuille",
        "portfolio",
        "trading",
        "trader",
    ],
    "crypto": [
        "crypto",
        "bitcoin",
        "ethereum",
        "blockchain",
        "nft",
        "defi",
        "web3",
        "token",
        "wallet",
        "portefeuille crypto",
        "mining",
        "minage",
        "altcoin",
        "staking",
    ],
    "fire": [
        "fire",
        "retraite anticipée",
        "early retirement",
        "indépendance financière",
        "financial independence",
        "liberté financière",
        "frugal",
        "épargne agressive",
        "taux d'épargne",
        "savings rate",
    ],
    "debt_free": [
        "dette",
        "debt",
        "rembourser",
        "pay off",
        "crédit",
        "credit",
        "prêt",
        "loan",
        "hypothèque",
        "mortgage payoff",
        "sans dette",
        "debt free",
        "consolidation",
        "surendettement",
    ],
    "passive_income": [
        "revenus passifs",
        "passive income",
        "revenus automatiques",
        "automatic income",
        "ebook",
        "cours en ligne",
        "online course",
        "affiliation",
        "affiliate",
        "royalties",
        "location",
        "rental income",
        "dividendes",
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
    "home_renovation": "Rénovation & Maison",
    "diy": "Bricolage & DIY",
    "parenting": "Parentalité & Famille",
    "pets": "Animaux & Soins",
    "gardening": "Jardinage & Agriculture",
    "real_estate": "Immobilier & Investissement",
    "retirement": "Retraite & Planification",
    "volunteer": "Bénévolat & Impact Social",
    "sobriety": "Sobriété & Rétablissement",
    "environmental": "Écologie & Mode de Vie Durable",
    "endurance": "Endurance & Courses",
    "martial_arts": "Arts Martiaux & Combat",
    "dance": "Danse",
    "outdoor": "Plein Air & Survie",
    "body_transformation": "Transformation Physique",
    "mental_health": "Santé Mentale",
    "sleep": "Sommeil & Récupération",
    "aging": "Bien Vieillir",
    "weight_management": "Gestion du Poids",
    "fertility": "Fertilité & Grossesse",
    "music_production": "Production Musicale",
    "writing": "Écriture & Publication",
    "fashion": "Mode & Style",
    "public_speaking": "Prise de Parole & Communication",
    "content_creation": "Création de Contenu",
    "minimalism": "Minimalisme & Simplicité",
    "digital_detox": "Détox Digitale & Tech Balance",
    "organization": "Organisation & Productivité Maison",
    "emigration": "Expatriation & Immigration",
    "event_planning": "Organisation d'Événements",
    "social_media": "Croissance Réseaux Sociaux",
    "podcast": "Podcast",
    "app_dev": "Développement d'Application",
    "book": "Écrire & Publier un Livre",
    "online_course": "Créer un Cours en Ligne",
    "research": "Recherche Académique",
    "competitive_exam": "Concours & Examens Compétitifs",
    "data_science": "Data Science & IA",
    "cybersecurity": "Cybersécurité",
    "teaching": "Enseignement & Mentorat",
    "automotive": "Automobile & Mécanique",
    "gaming": "Gaming & Esports",
    "culinary": "Cuisine Avancée & Gastronomie",
    "photography": "Photo & Vidéo",
    "spirituality": "Spiritualité & Bien-être",
    "relocation": "Déménagement",
    "wedding": "Mariage",
    "car_purchase": "Achat de Véhicule",
    "immersion": "Immersion Linguistique",
    "digital_nomad": "Nomade Digital",
    "driving": "Permis de Conduire",
    "extreme_sports": "Sports Extrêmes",
    "retirement_hobby": "Loisirs à la Retraite",
    "competition": "Préparation Compétition",
    "life_transition": "Transition de Vie",
    "dating": "Rencontres & Séduction",
    "confidence": "Confiance en Soi",
    "leadership": "Leadership & Management",
    "networking": "Réseautage Professionnel",
    "communication": "Communication & Expression",
    "startup": "Startup & Innovation",
    "freelance": "Freelance & Indépendant",
    "side_hustle": "Side Hustle & Revenus Complémentaires",
    "ecommerce": "E-Commerce & Vente en Ligne",
    "nonprofit": "Association & ONG",
    "prepping": "Préparation aux Urgences",
    "instrument": "Maîtrise d'un Instrument",
    "visual_art": "Arts Visuels",
    "collecting": "Collection & Hobby",
    "urban_farming": "Agriculture Urbaine",
    "investing": "Investissement & Bourse",
    "crypto": "Crypto & Blockchain",
    "fire": "FIRE & Retraite Anticipée",
    "debt_free": "Zéro Dettes",
    "passive_income": "Revenus Passifs",
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
