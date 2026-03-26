"""Management command to seed dream templates."""

from django.core.management.base import BaseCommand

from apps.dreams.models import DreamTemplate


class Command(BaseCommand):
    help = "Seed dream templates covering all 10 categories (at least 5 per category)"

    # ─────────────────────────────────────────────────────────────────
    # Helper: build a compact template dict
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _tpl(
        title,
        description,
        category,
        difficulty,
        days,
        timeline,
        icon,
        color,
        featured,
        goals,
    ):
        return {
            "title": title,
            "description": description,
            "category": category,
            "difficulty": difficulty,
            "estimated_duration_days": days,
            "suggested_timeline": timeline,
            "icon": icon,
            "color": color,
            "is_featured": featured,
            "template_goals": goals,
        }

    @staticmethod
    def _goal(title, description, order, tasks):
        return {
            "title": title,
            "description": description,
            "order": order,
            "tasks": tasks,
        }

    @staticmethod
    def _task(title, order, mins):
        return {"title": title, "order": order, "duration_mins": mins}

    # ─────────────────────────────────────────────────────────────────
    # Templates
    # ─────────────────────────────────────────────────────────────────
    def _health_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Run a Marathon",
                "Train progressively to complete a full 42km marathon. From couch to finish line with structured training.",
                "health", "advanced", 180, "6 months", "running", "#EF4444", True,
                [
                    g("Build base fitness", "Establish a running routine", 1, [
                        t("Run 2km three times this week", 1, 20),
                        t("Do stretching routine after each run", 2, 10),
                        t("Track runs in a journal", 3, 5),
                    ]),
                    g("Increase distance", "Progressively increase weekly distance", 2, [
                        t("Run 5km twice this week", 1, 35),
                        t("One long run of 8km this week", 2, 55),
                        t("Cross-train with cycling or swimming", 3, 45),
                    ]),
                    g("Race preparation", "Taper and prepare for race day", 3, [
                        t("Register for the marathon event", 1, 15),
                        t("Do a half-marathon practice run", 2, 120),
                        t("Plan race day nutrition and gear", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Build a Meditation Practice",
                "Develop a consistent daily meditation habit starting from just 5 minutes a day, building up to 30-minute sessions.",
                "health", "beginner", 60, "2 months", "brain", "#10B981", False,
                [
                    g("Start with 5-minute sessions", "Build the daily habit with short sessions", 1, [
                        t("Download a meditation app", 1, 10),
                        t("Meditate for 5 minutes", 2, 5),
                        t("Journal how you feel after each session", 3, 5),
                    ]),
                    g("Extend to 15 minutes", "Gradually increase session length", 2, [
                        t("Try a guided body scan meditation", 1, 15),
                        t("Practice breathing exercises", 2, 10),
                        t("Meditate without guidance for 10 minutes", 3, 10),
                    ]),
                    g("Reach 30-minute sessions", "Sustain longer focused meditation", 3, [
                        t("Complete a 30-minute seated meditation", 1, 30),
                        t("Try a walking meditation outdoors", 2, 20),
                        t("Teach someone else a basic technique", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Lose 20 Pounds",
                "Achieve sustainable weight loss through balanced nutrition, regular exercise, and healthy habits.",
                "health", "intermediate", 120, "4 months", "scale", "#F97316", False,
                [
                    g("Audit your current habits", "Understand where you are today", 1, [
                        t("Track everything you eat for one week", 1, 15),
                        t("Calculate your daily caloric needs", 2, 20),
                        t("Take baseline body measurements and photos", 3, 10),
                    ]),
                    g("Build a nutrition plan", "Create a sustainable eating pattern", 2, [
                        t("Plan a week of healthy meals", 1, 30),
                        t("Meal-prep for the week", 2, 60),
                        t("Replace sugary drinks with water for one week", 3, 5),
                    ]),
                    g("Add regular exercise", "Move your body consistently", 3, [
                        t("Exercise for 30 minutes three times this week", 1, 30),
                        t("Try a new workout class or sport", 2, 45),
                        t("Walk 10,000 steps daily for a week", 3, 15),
                    ]),
                    g("Stay on track", "Monitor progress and adjust", 4, [
                        t("Weigh yourself once a week and log it", 1, 5),
                        t("Adjust meal plan based on results", 2, 20),
                        t("Celebrate each 5-pound milestone", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Complete a Triathlon",
                "Train for and finish a sprint triathlon: 750m swim, 20km bike, 5km run.",
                "health", "advanced", 120, "4 months", "trophy", "#0EA5E9", False,
                [
                    g("Assess and equip", "Get gear and baseline fitness", 1, [
                        t("Get a bike fit and check equipment", 1, 30),
                        t("Swim 400m to gauge starting level", 2, 25),
                        t("Run 2km at comfortable pace", 3, 15),
                    ]),
                    g("Build each discipline", "Train swim, bike, and run individually", 2, [
                        t("Swim drills twice a week for 30 min", 1, 30),
                        t("Bike 15km once this week", 2, 45),
                        t("Run 3km three times this week", 3, 25),
                    ]),
                    g("Brick workouts", "Practice back-to-back disciplines", 3, [
                        t("Bike 15km then run 3km immediately after", 1, 60),
                        t("Swim 750m then bike 10km", 2, 50),
                        t("Simulate full race distance at easy pace", 3, 90),
                    ]),
                    g("Race day prep", "Taper and finalize logistics", 4, [
                        t("Register for the triathlon event", 1, 15),
                        t("Practice transitions (T1 and T2)", 2, 20),
                        t("Plan nutrition and gear checklist", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Master Yoga",
                "Progress from beginner to advanced yoga, building flexibility, strength, and mindfulness over 6 months.",
                "health", "intermediate", 180, "6 months", "flower-2", "#A855F7", False,
                [
                    g("Learn foundational poses", "Build a solid base", 1, [
                        t("Attend a beginner yoga class or follow a video", 1, 45),
                        t("Learn Sun Salutation A and B", 2, 30),
                        t("Practice 5 basic poses daily for a week", 3, 20),
                    ]),
                    g("Build a home practice", "Develop consistency without a class", 2, [
                        t("Set up a dedicated practice space", 1, 15),
                        t("Follow a 30-minute flow 4 times this week", 2, 30),
                        t("Learn 3 balancing poses", 3, 25),
                    ]),
                    g("Deepen your practice", "Work toward intermediate and advanced poses", 3, [
                        t("Hold Crow Pose for 10 seconds", 1, 20),
                        t("Complete a 60-minute power yoga session", 2, 60),
                        t("Integrate pranayama breathing into practice", 3, 15),
                    ]),
                ],
            ),
        ]

    def _career_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Get a Promotion",
                "Strategically position yourself for a career advancement within your current company.",
                "career", "intermediate", 120, "4 months", "briefcase", "#3B82F6", True,
                [
                    g("Assess current position", "Understand what is needed for advancement", 1, [
                        t("Research the requirements for the next role", 1, 30),
                        t("Schedule a 1-on-1 with your manager", 2, 30),
                        t("Identify skill gaps", 3, 20),
                    ]),
                    g("Build visibility", "Increase your visibility within the organization", 2, [
                        t("Volunteer for a high-visibility project", 1, 15),
                        t("Present at a team meeting", 2, 45),
                        t("Document your achievements", 3, 20),
                    ]),
                    g("Make the ask", "Formally request the promotion", 3, [
                        t("Prepare a promotion case document", 1, 60),
                        t("Schedule a formal review meeting", 2, 10),
                        t("Negotiate salary and title", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Launch a Side Business",
                "Go from idea to first paying customer. Validate your business idea and build an MVP.",
                "career", "advanced", 90, "3 months", "rocket", "#6366F1", True,
                [
                    g("Validate the idea", "Research market fit and demand", 1, [
                        t("Interview 5 potential customers", 1, 60),
                        t("Research competitors and pricing", 2, 45),
                        t("Write a one-page business plan", 3, 30),
                    ]),
                    g("Build the MVP", "Create a minimum viable product", 2, [
                        t("Define the core feature set", 1, 30),
                        t("Build or prototype the product", 2, 120),
                        t("Set up a simple landing page", 3, 60),
                    ]),
                    g("Get first customers", "Launch and acquire initial users", 3, [
                        t("Announce to your network", 1, 20),
                        t("Reach out to 10 potential customers", 2, 45),
                        t("Collect feedback and iterate", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Land a Senior Developer Role",
                "Level up your technical skills and interview readiness to secure a senior software engineering position.",
                "career", "advanced", 180, "6 months", "code", "#8B5CF6", False,
                [
                    g("Strengthen fundamentals", "Close gaps in data structures, algorithms, and system design", 1, [
                        t("Complete 50 LeetCode problems (medium difficulty)", 1, 60),
                        t("Study one system design topic per week", 2, 45),
                        t("Read a software architecture book", 3, 30),
                    ]),
                    g("Build portfolio projects", "Demonstrate senior-level work", 2, [
                        t("Contribute to an open-source project", 1, 60),
                        t("Build a full-stack project with CI/CD", 2, 120),
                        t("Write a technical blog post", 3, 45),
                    ]),
                    g("Interview preparation", "Practice and apply", 3, [
                        t("Do 3 mock interviews with peers", 1, 60),
                        t("Update resume and LinkedIn profile", 2, 30),
                        t("Apply to 10 target companies", 3, 45),
                    ]),
                ],
            ),
            self._tpl(
                "Build a Personal Brand",
                "Establish yourself as a recognized voice in your industry through content creation and networking.",
                "career", "intermediate", 180, "6 months", "megaphone", "#F59E0B", False,
                [
                    g("Define your brand", "Clarify your niche and message", 1, [
                        t("Identify your top 3 areas of expertise", 1, 20),
                        t("Write a compelling bio and elevator pitch", 2, 25),
                        t("Audit and update all social profiles", 3, 30),
                    ]),
                    g("Create content consistently", "Publish valuable content on a schedule", 2, [
                        t("Write and publish one article per week", 1, 60),
                        t("Post 3 times per week on LinkedIn or Twitter", 2, 20),
                        t("Record a short video or podcast episode", 3, 45),
                    ]),
                    g("Grow your network", "Connect with industry peers and audience", 3, [
                        t("Attend one networking event or webinar per month", 1, 30),
                        t("Reach out to 5 people you admire in your field", 2, 20),
                        t("Guest post or collaborate with another creator", 3, 45),
                    ]),
                ],
            ),
            self._tpl(
                "Career Change to Tech",
                "Transition into a tech career from a non-technical background through structured learning and networking.",
                "career", "advanced", 365, "12 months", "laptop", "#06B6D4", False,
                [
                    g("Choose your path", "Decide which tech role suits you", 1, [
                        t("Research 5 different tech career paths", 1, 30),
                        t("Talk to 3 people already in those roles", 2, 45),
                        t("Decide on your target role and required skills", 3, 20),
                    ]),
                    g("Learn core skills", "Complete foundational training", 2, [
                        t("Enroll in an online course or bootcamp", 1, 15),
                        t("Study 1 hour daily for 3 months", 2, 60),
                        t("Build 3 portfolio projects", 3, 120),
                    ]),
                    g("Build your network", "Connect with the tech community", 3, [
                        t("Join 2 tech communities or Slack groups", 1, 15),
                        t("Attend a local tech meetup or virtual event", 2, 30),
                        t("Find a mentor in your target role", 3, 20),
                    ]),
                    g("Job search", "Apply and interview strategically", 4, [
                        t("Tailor resume for tech roles", 1, 30),
                        t("Apply to 5 roles per week", 2, 30),
                        t("Practice technical interviews", 3, 60),
                    ]),
                ],
            ),
        ]

    def _finance_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Save an Emergency Fund",
                "Build a 6-month emergency fund through systematic saving and expense optimization.",
                "finance", "beginner", 180, "6 months", "piggy-bank", "#F59E0B", False,
                [
                    g("Analyze finances", "Understand your current financial situation", 1, [
                        t("Calculate monthly expenses", 1, 30),
                        t("Set a target emergency fund amount", 2, 15),
                        t("Identify areas to cut spending", 3, 20),
                    ]),
                    g("Automate savings", "Set up automatic transfers", 2, [
                        t("Open a high-yield savings account", 1, 20),
                        t("Set up automatic monthly transfer", 2, 10),
                        t("Review and adjust budget weekly", 3, 15),
                    ]),
                    g("Reach the goal", "Complete the emergency fund", 3, [
                        t("Track progress monthly", 1, 10),
                        t("Find one additional income source", 2, 30),
                        t("Celebrate reaching the milestone", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Start Investing",
                "Learn the fundamentals of investing and make your first investment with confidence.",
                "finance", "intermediate", 60, "2 months", "trending-up", "#22C55E", True,
                [
                    g("Learn the basics", "Understand investment fundamentals", 1, [
                        t("Learn the difference between stocks, bonds, and ETFs", 1, 30),
                        t("Understand risk tolerance and asset allocation", 2, 25),
                        t("Research low-cost index fund options", 3, 20),
                    ]),
                    g("Set up your accounts", "Open brokerage and start contributing", 2, [
                        t("Open a brokerage account", 1, 20),
                        t("Set up automatic monthly contributions", 2, 10),
                        t("Make your first investment", 3, 15),
                    ]),
                    g("Build long-term habits", "Create a sustainable investing routine", 3, [
                        t("Review your portfolio monthly", 1, 15),
                        t("Read one investing article per week", 2, 15),
                        t("Rebalance portfolio if needed", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Pay Off Debt",
                "Eliminate outstanding debt using a structured payoff strategy like the snowball or avalanche method.",
                "finance", "intermediate", 365, "12 months", "credit-card", "#EF4444", True,
                [
                    g("Get organized", "List all debts and create a plan", 1, [
                        t("List all debts with balances, rates, and minimums", 1, 30),
                        t("Choose snowball (smallest first) or avalanche (highest rate first)", 2, 15),
                        t("Calculate total monthly payment budget", 3, 20),
                    ]),
                    g("Optimize spending", "Free up extra cash for payments", 2, [
                        t("Cancel unused subscriptions", 1, 20),
                        t("Create a bare-bones budget for one month", 2, 25),
                        t("Find one way to earn extra income", 3, 30),
                    ]),
                    g("Execute the plan", "Make consistent payments", 3, [
                        t("Make extra payment on target debt this month", 1, 10),
                        t("Track progress on a visual debt thermometer", 2, 10),
                        t("Celebrate each debt fully paid off", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Create a Budget That Works",
                "Design a personal budget system you can actually stick to, giving every dollar a purpose.",
                "finance", "beginner", 30, "1 month", "wallet", "#F97316", False,
                [
                    g("Track current spending", "Understand where your money goes", 1, [
                        t("Record every expense for 2 weeks", 1, 10),
                        t("Categorize expenses (needs, wants, savings)", 2, 20),
                        t("Identify your top 3 spending leaks", 3, 15),
                    ]),
                    g("Build the budget", "Create a realistic plan", 2, [
                        t("Choose a budgeting method (50/30/20, zero-based, etc.)", 1, 15),
                        t("Set up a budgeting app or spreadsheet", 2, 20),
                        t("Allocate amounts to each category", 3, 15),
                    ]),
                    g("Stick to it", "Follow the budget for a full month", 3, [
                        t("Check spending against budget mid-week", 1, 10),
                        t("Adjust categories if something is unrealistic", 2, 10),
                        t("Review month-end results and refine", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Build Passive Income Streams",
                "Create one or more sources of passive income that generate money while you sleep.",
                "finance", "advanced", 180, "6 months", "banknote", "#8B5CF6", False,
                [
                    g("Research passive income ideas", "Find the right fit for your skills and capital", 1, [
                        t("List 10 passive income ideas and rank feasibility", 1, 30),
                        t("Calculate startup cost and time investment for top 3", 2, 25),
                        t("Pick one idea to pursue first", 3, 10),
                    ]),
                    g("Build the asset", "Create the product or investment", 2, [
                        t("Create an outline or plan for your asset", 1, 30),
                        t("Dedicate 1 hour daily to building it", 2, 60),
                        t("Set up payment or distribution infrastructure", 3, 30),
                    ]),
                    g("Launch and optimize", "Go live and improve", 3, [
                        t("Launch to a small test audience", 1, 20),
                        t("Track revenue weekly and identify improvements", 2, 15),
                        t("Automate or delegate routine tasks", 3, 25),
                    ]),
                ],
            ),
        ]

    def _personal_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Build a Morning Routine",
                "Design and stick to a powerful morning routine that sets you up for success every day.",
                "personal", "beginner", 30, "1 month", "sunrise", "#F97316", False,
                [
                    g("Design the routine", "Plan your ideal morning", 1, [
                        t("Research morning routine ideas", 1, 20),
                        t("Write out your ideal morning hour by hour", 2, 15),
                        t("Prepare everything the night before", 3, 15),
                    ]),
                    g("Build the habit", "Practice for 21 days", 2, [
                        t("Wake up at target time", 1, 5),
                        t("Complete morning routine", 2, 60),
                        t("Rate how the morning went (1-10)", 3, 5),
                    ]),
                ],
            ),
            self._tpl(
                "Read 20 Books This Year",
                "Cultivate a consistent reading habit and expand your knowledge by completing 20 books.",
                "personal", "intermediate", 365, "1 year", "book-open", "#8B5CF6", True,
                [
                    g("Set up your reading system", "Create a reading list and schedule", 1, [
                        t("Create a list of 25 books to choose from", 1, 30),
                        t("Set a daily reading time (30 min minimum)", 2, 10),
                        t("Join a book club or find a reading buddy", 3, 15),
                    ]),
                    g("Build the habit", "Read consistently for the first month", 2, [
                        t("Read for 30 minutes today", 1, 30),
                        t("Write a brief summary of what you read", 2, 10),
                        t("Finish your first book", 3, 30),
                    ]),
                    g("Stay on track", "Maintain pace of ~2 books per month", 3, [
                        t("Review your reading log", 1, 10),
                        t("Share a book recommendation with someone", 2, 10),
                        t("Adjust your reading list based on interests", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Develop a Journaling Habit",
                "Write daily to boost self-awareness, process emotions, and track personal growth.",
                "personal", "beginner", 60, "2 months", "pen-line", "#10B981", False,
                [
                    g("Start simple", "Build the daily writing habit", 1, [
                        t("Choose a journal format (notebook or app)", 1, 10),
                        t("Write 3 sentences about your day", 2, 10),
                        t("Journal at the same time daily for one week", 3, 10),
                    ]),
                    g("Deepen your practice", "Explore different journaling styles", 2, [
                        t("Try gratitude journaling for a week", 1, 10),
                        t("Write a stream-of-consciousness entry", 2, 15),
                        t("Use prompts to explore a challenging topic", 3, 15),
                    ]),
                    g("Make it a lifestyle", "Sustain the habit long-term", 3, [
                        t("Review past entries and note patterns", 1, 15),
                        t("Write a letter to your future self", 2, 20),
                        t("Celebrate 30 consecutive days of journaling", 3, 5),
                    ]),
                ],
            ),
            self._tpl(
                "Digital Detox",
                "Reduce screen time and reclaim your attention by building healthier digital habits.",
                "personal", "intermediate", 30, "1 month", "smartphone", "#EF4444", False,
                [
                    g("Audit your screen time", "Understand your current usage", 1, [
                        t("Check screen time stats on your phone", 1, 10),
                        t("Identify your top 3 time-wasting apps", 2, 10),
                        t("Set daily screen time goals", 3, 10),
                    ]),
                    g("Create boundaries", "Implement changes to reduce usage", 2, [
                        t("Turn off non-essential notifications", 1, 10),
                        t("Designate phone-free zones (bedroom, meals)", 2, 5),
                        t("Replace 30 min of scrolling with a hobby", 3, 30),
                    ]),
                    g("Build offline habits", "Fill reclaimed time with enriching activities", 3, [
                        t("Spend an evening without screens", 1, 60),
                        t("Pick up a physical book or board game", 2, 30),
                        t("Reflect on how reduced screen time feels", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Learn a New Language",
                "Reach conversational fluency in a new language through daily practice and immersion.",
                "personal", "intermediate", 180, "6 months", "languages", "#3B82F6", True,
                [
                    g("Get started", "Set up tools and learn basics", 1, [
                        t("Choose a language learning app (Duolingo, Babbel, etc.)", 1, 10),
                        t("Learn 50 essential words and phrases", 2, 30),
                        t("Practice pronunciation with audio resources", 3, 20),
                    ]),
                    g("Build daily practice", "Make it a consistent habit", 2, [
                        t("Study for 20 minutes every day", 1, 20),
                        t("Watch a show or video in the target language", 2, 30),
                        t("Label 10 objects at home in the new language", 3, 10),
                    ]),
                    g("Practice conversation", "Use the language with real people", 3, [
                        t("Have a 10-minute conversation with a native speaker", 1, 15),
                        t("Write a short journal entry in the new language", 2, 15),
                        t("Order food or ask directions in the language", 3, 10),
                    ]),
                ],
            ),
        ]

    def _hobbies_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Learn to Play Guitar",
                "Go from zero to playing your first song. Learn chords, strumming patterns, and basic music theory.",
                "hobbies", "beginner", 90, "3 months", "music", "#EC4899", False,
                [
                    g("Get started", "Set up your instrument and learn basics", 1, [
                        t("Get a guitar (buy or borrow)", 1, 30),
                        t("Learn to tune the guitar", 2, 15),
                        t("Learn 3 basic chords (G, C, D)", 3, 30),
                    ]),
                    g("Practice chord transitions", "Build muscle memory and fluidity", 2, [
                        t("Practice switching between chords for 15 minutes", 1, 15),
                        t("Learn a basic strumming pattern", 2, 20),
                        t("Learn 3 more chords (Am, Em, F)", 3, 30),
                    ]),
                    g("Play your first song", "Put it all together", 3, [
                        t("Choose a simple song to learn", 1, 10),
                        t("Practice the song section by section", 2, 30),
                        t("Play the full song start to finish", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Start a Photography Hobby",
                "Learn photography fundamentals and build a portfolio of shots you are proud of.",
                "hobbies", "intermediate", 60, "2 months", "camera", "#14B8A6", False,
                [
                    g("Learn the basics", "Understand camera settings and composition", 1, [
                        t("Learn about aperture, shutter speed, and ISO", 1, 30),
                        t("Practice the rule of thirds composition", 2, 20),
                        t("Take 50 photos exploring different settings", 3, 45),
                    ]),
                    g("Develop your eye", "Practice different genres and styles", 2, [
                        t("Do a golden hour photo walk", 1, 60),
                        t("Try street photography for 30 minutes", 2, 30),
                        t("Learn basic photo editing", 3, 45),
                    ]),
                    g("Build your portfolio", "Select and present your best work", 3, [
                        t("Select your 10 best photos", 1, 20),
                        t("Edit and finalize each photo", 2, 60),
                        t("Create an online portfolio or Instagram", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Learn to Cook Like a Chef",
                "Master essential cooking techniques and build a repertoire of 20 recipes you can make from memory.",
                "hobbies", "intermediate", 90, "3 months", "chef-hat", "#F59E0B", False,
                [
                    g("Master the basics", "Learn fundamental kitchen skills", 1, [
                        t("Learn proper knife skills (dicing, mincing, julienne)", 1, 30),
                        t("Master 3 basic cooking methods (sauté, roast, boil)", 2, 45),
                        t("Cook 5 simple one-pot meals", 3, 40),
                    ]),
                    g("Expand your repertoire", "Learn new cuisines and techniques", 2, [
                        t("Try a recipe from a cuisine you've never cooked", 1, 60),
                        t("Learn to make a homemade sauce or dressing", 2, 30),
                        t("Cook a full 3-course meal", 3, 90),
                    ]),
                    g("Cook from memory", "Internalize your favorite dishes", 3, [
                        t("Cook 3 dishes without following a recipe", 1, 45),
                        t("Host a dinner for friends or family", 2, 120),
                        t("Create your own signature dish", 3, 60),
                    ]),
                ],
            ),
            self._tpl(
                "Start a Garden",
                "Grow your own herbs, vegetables, or flowers from seed to harvest, even in a small space.",
                "hobbies", "beginner", 120, "4 months", "sprout", "#22C55E", False,
                [
                    g("Plan your garden", "Decide what to grow and where", 1, [
                        t("Research what grows well in your climate zone", 1, 20),
                        t("Choose 5 plants to start with", 2, 15),
                        t("Get supplies (soil, pots, seeds, tools)", 3, 30),
                    ]),
                    g("Plant and care", "Get seeds in the ground and nurture them", 2, [
                        t("Plant seeds or seedlings following spacing guidelines", 1, 30),
                        t("Set up a watering schedule", 2, 10),
                        t("Learn about common pests and how to prevent them", 3, 20),
                    ]),
                    g("Harvest and enjoy", "Reap the rewards of your work", 3, [
                        t("Harvest your first crop", 1, 15),
                        t("Cook a meal with ingredients from your garden", 2, 45),
                        t("Plan next season's garden based on lessons learned", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Learn to Draw",
                "Develop drawing skills from scratch, building confidence with pencil and paper through daily practice.",
                "hobbies", "beginner", 90, "3 months", "pencil", "#6366F1", False,
                [
                    g("Learn fundamentals", "Understand basic drawing principles", 1, [
                        t("Practice drawing basic shapes (circles, cubes, cylinders)", 1, 20),
                        t("Learn about light, shadow, and shading", 2, 25),
                        t("Complete a contour drawing exercise", 3, 15),
                    ]),
                    g("Daily sketching habit", "Draw something every single day", 2, [
                        t("Sketch for 15 minutes daily for 2 weeks", 1, 15),
                        t("Draw 5 everyday objects from observation", 2, 20),
                        t("Try a different subject each day (nature, people, buildings)", 3, 20),
                    ]),
                    g("Create finished pieces", "Produce artwork you are proud of", 3, [
                        t("Complete a detailed still-life drawing", 1, 45),
                        t("Draw a portrait from a photo reference", 2, 40),
                        t("Share your work and get feedback", 3, 15),
                    ]),
                ],
            ),
        ]

    def _relationships_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Strengthen Relationships",
                "Deepen connections with family and friends through intentional quality time and meaningful gestures.",
                "relationships", "beginner", 60, "2 months", "heart", "#F43F5E", False,
                [
                    g("Reconnect", "Reach out to people you have lost touch with", 1, [
                        t("Make a list of 10 people to reconnect with", 1, 15),
                        t("Send a message to 3 people today", 2, 15),
                        t("Schedule a catch-up call or coffee", 3, 10),
                    ]),
                    g("Quality time", "Plan meaningful experiences", 2, [
                        t("Plan a special activity with a loved one", 1, 15),
                        t("Have a deep conversation (no phones)", 2, 30),
                        t("Write a heartfelt note to someone", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Become a Better Listener",
                "Improve your listening and communication skills to build deeper, more meaningful relationships.",
                "relationships", "beginner", 30, "1 month", "ear", "#A855F7", False,
                [
                    g("Learn active listening", "Study and practice core techniques", 1, [
                        t("Read about active listening techniques", 1, 20),
                        t("Practice mirroring in a conversation", 2, 15),
                        t("Ask 3 open-ended questions in your next chat", 3, 10),
                    ]),
                    g("Apply daily", "Use techniques in real conversations", 2, [
                        t("Have a conversation where you only listen", 1, 20),
                        t("Summarize what someone said back to them", 2, 10),
                        t("Journal about what you learned from listening", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Improve Your Marriage or Partnership",
                "Invest in your romantic relationship with intentional date nights, communication, and shared goals.",
                "relationships", "intermediate", 90, "3 months", "heart-handshake", "#EC4899", False,
                [
                    g("Assess and communicate", "Have honest conversations about the relationship", 1, [
                        t("Share 3 things you appreciate about your partner", 1, 10),
                        t("Discuss one area each person wants to improve", 2, 20),
                        t("Set 3 shared relationship goals", 3, 15),
                    ]),
                    g("Prioritize quality time", "Schedule regular meaningful time together", 2, [
                        t("Plan a weekly date night for one month", 1, 15),
                        t("Try a new activity together", 2, 60),
                        t("Spend 15 minutes daily in device-free conversation", 3, 15),
                    ]),
                    g("Build deeper connection", "Strengthen emotional intimacy", 3, [
                        t("Ask your partner a deep question from a conversation deck", 1, 15),
                        t("Write a love letter or gratitude note", 2, 20),
                        t("Plan a surprise for your partner", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Build a Support Network",
                "Create a strong circle of friends and mentors who support your growth and well-being.",
                "relationships", "intermediate", 90, "3 months", "users", "#3B82F6", False,
                [
                    g("Identify your needs", "Understand what kind of support you need", 1, [
                        t("List areas where you need support (career, emotional, social)", 1, 15),
                        t("Identify 5 people who could fill each role", 2, 15),
                        t("Reach out to one potential mentor", 3, 15),
                    ]),
                    g("Nurture existing connections", "Strengthen bonds with current friends", 2, [
                        t("Schedule a monthly check-in with 3 close friends", 1, 10),
                        t("Offer help to someone in your network", 2, 20),
                        t("Host a small gathering or virtual hangout", 3, 30),
                    ]),
                    g("Expand your circle", "Meet new people aligned with your values", 3, [
                        t("Join a community group, club, or class", 1, 15),
                        t("Attend a social event and introduce yourself to 3 people", 2, 30),
                        t("Follow up with a new connection within 48 hours", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Be a Better Parent",
                "Strengthen your parenting through more presence, patience, and intentional quality time with your kids.",
                "relationships", "intermediate", 60, "2 months", "baby", "#F97316", False,
                [
                    g("Be more present", "Reduce distractions and increase connection", 1, [
                        t("Spend 20 minutes of undivided attention with each child daily", 1, 20),
                        t("Put your phone away during family meals", 2, 5),
                        t("Ask your child about the best and worst parts of their day", 3, 10),
                    ]),
                    g("Create rituals", "Build meaningful family traditions", 2, [
                        t("Start a weekly family activity (game night, hike, cooking)", 1, 60),
                        t("Read together before bed for a week", 2, 20),
                        t("Create a family gratitude jar", 3, 10),
                    ]),
                    g("Grow as a parent", "Learn and reflect on your parenting", 3, [
                        t("Read a parenting book or article each week", 1, 20),
                        t("Practice one new positive discipline technique", 2, 10),
                        t("Journal about a parenting win and a lesson learned", 3, 10),
                    ]),
                ],
            ),
        ]

    def _education_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Complete an Online Certification",
                "Earn a professional certification to boost your resume and skills in your field.",
                "education", "intermediate", 90, "3 months", "graduation-cap", "#3B82F6", True,
                [
                    g("Choose and enroll", "Select the right certification program", 1, [
                        t("Research 5 certifications relevant to your goals", 1, 30),
                        t("Compare cost, duration, and recognition", 2, 20),
                        t("Enroll and set up your study schedule", 3, 15),
                    ]),
                    g("Study consistently", "Complete the coursework", 2, [
                        t("Study for 1 hour daily", 1, 60),
                        t("Complete all practice exercises and quizzes", 2, 30),
                        t("Join a study group or forum", 3, 15),
                    ]),
                    g("Pass the exam", "Prepare for and ace the certification exam", 3, [
                        t("Take 3 full practice exams", 1, 60),
                        t("Review weak areas identified in practice tests", 2, 30),
                        t("Schedule and pass the certification exam", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Learn to Code",
                "Go from zero programming knowledge to building your first web application.",
                "education", "beginner", 120, "4 months", "code-2", "#8B5CF6", True,
                [
                    g("Foundations", "Learn the basics of programming", 1, [
                        t("Choose a language (Python, JavaScript, etc.)", 1, 15),
                        t("Complete an intro course (variables, loops, functions)", 2, 60),
                        t("Write your first 'Hello World' program", 3, 10),
                    ]),
                    g("Build skills", "Work on progressively harder projects", 2, [
                        t("Build a simple calculator", 1, 45),
                        t("Create a to-do list application", 2, 60),
                        t("Learn about databases and APIs", 3, 45),
                    ]),
                    g("Launch a project", "Build and deploy something real", 3, [
                        t("Design a personal project idea", 1, 20),
                        t("Build the project over 2 weeks", 2, 120),
                        t("Deploy it online and share with others", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Master Public Speaking",
                "Overcome fear of public speaking and deliver confident presentations to any audience.",
                "education", "intermediate", 90, "3 months", "mic", "#F43F5E", False,
                [
                    g("Build confidence", "Start small and build up", 1, [
                        t("Record yourself speaking for 2 minutes on any topic", 1, 10),
                        t("Watch the recording and note 3 areas to improve", 2, 10),
                        t("Practice a 1-minute elevator pitch in front of a mirror", 3, 10),
                    ]),
                    g("Learn structure and technique", "Study great speakers", 2, [
                        t("Watch 3 TED talks and analyze their structure", 1, 30),
                        t("Write and rehearse a 5-minute speech", 2, 30),
                        t("Practice controlling pace, pauses, and eye contact", 3, 15),
                    ]),
                    g("Speak to a real audience", "Practice in front of people", 3, [
                        t("Present to a small group of friends or colleagues", 1, 20),
                        t("Join a Toastmasters club or speaking group", 2, 15),
                        t("Deliver a 10-minute presentation and collect feedback", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Study for a Major Exam",
                "Prepare methodically for a standardized test (SAT, GRE, GMAT, bar exam, etc.) and hit your target score.",
                "education", "advanced", 120, "4 months", "file-text", "#F59E0B", False,
                [
                    g("Diagnostic and planning", "Understand where you stand", 1, [
                        t("Take a full diagnostic practice test", 1, 120),
                        t("Analyze results and identify weak sections", 2, 30),
                        t("Create a weekly study plan targeting weak areas", 3, 20),
                    ]),
                    g("Deep study phase", "Build knowledge and skills systematically", 2, [
                        t("Study 1-2 hours daily following your plan", 1, 90),
                        t("Complete one practice section per week", 2, 45),
                        t("Review all incorrect answers and understand why", 3, 30),
                    ]),
                    g("Test readiness", "Simulate real test conditions", 3, [
                        t("Take 3 full-length practice tests under timed conditions", 1, 120),
                        t("Refine time management strategy", 2, 20),
                        t("Rest well the week before the exam", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Learn Data Science",
                "Build practical data science skills: statistics, Python, visualization, and machine learning basics.",
                "education", "intermediate", 180, "6 months", "bar-chart-3", "#06B6D4", False,
                [
                    g("Statistics and Python basics", "Build the foundation", 1, [
                        t("Complete a statistics fundamentals course", 1, 60),
                        t("Learn Python basics (pandas, numpy)", 2, 60),
                        t("Analyze a public dataset and create a summary", 3, 45),
                    ]),
                    g("Visualization and storytelling", "Learn to communicate with data", 2, [
                        t("Learn matplotlib or seaborn for data visualization", 1, 45),
                        t("Create 5 different chart types from real data", 2, 30),
                        t("Build a data dashboard or report", 3, 60),
                    ]),
                    g("Machine learning intro", "Build your first predictive model", 3, [
                        t("Complete a scikit-learn tutorial", 1, 60),
                        t("Build a classification model on a real dataset", 2, 90),
                        t("Present your findings in a Jupyter notebook", 3, 30),
                    ]),
                ],
            ),
        ]

    def _creative_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Write a Novel",
                "Plan, draft, and complete a full-length novel of 50,000+ words.",
                "creative", "advanced", 180, "6 months", "book", "#8B5CF6", True,
                [
                    g("Plan your story", "Outline plot, characters, and world", 1, [
                        t("Write character profiles for 3 main characters", 1, 30),
                        t("Create a chapter-by-chapter outline", 2, 45),
                        t("Define the core theme and conflict", 3, 20),
                    ]),
                    g("Write the first draft", "Get the story on paper", 2, [
                        t("Write 1,000 words per day", 1, 60),
                        t("Complete the first act (chapters 1-10)", 2, 60),
                        t("Push through the middle without editing", 3, 60),
                    ]),
                    g("Revise and polish", "Turn the draft into a finished manuscript", 3, [
                        t("Read through the entire draft and take notes", 1, 120),
                        t("Revise for plot holes and character consistency", 2, 90),
                        t("Get feedback from 2 beta readers", 3, 30),
                    ]),
                ],
            ),
            self._tpl(
                "Start a YouTube Channel",
                "Launch a YouTube channel, publish your first 10 videos, and build an initial audience.",
                "creative", "intermediate", 90, "3 months", "video", "#EF4444", True,
                [
                    g("Plan your channel", "Define your niche and brand", 1, [
                        t("Choose your niche and target audience", 1, 20),
                        t("Study 5 successful channels in your niche", 2, 30),
                        t("Create channel art, logo, and description", 3, 30),
                    ]),
                    g("Create your first videos", "Produce and publish content", 2, [
                        t("Script your first video", 1, 30),
                        t("Film and edit your first video", 2, 90),
                        t("Publish 3 videos in your first month", 3, 60),
                    ]),
                    g("Grow your audience", "Promote and engage consistently", 3, [
                        t("Optimize titles, thumbnails, and descriptions for SEO", 1, 20),
                        t("Reply to every comment for the first month", 2, 15),
                        t("Publish consistently (1 video per week)", 3, 60),
                    ]),
                ],
            ),
            self._tpl(
                "Learn Digital Art",
                "Master digital illustration using a tablet and software like Procreate or Photoshop.",
                "creative", "beginner", 90, "3 months", "palette", "#EC4899", False,
                [
                    g("Set up your tools", "Get the right software and hardware", 1, [
                        t("Choose and set up drawing software (Procreate, Krita, etc.)", 1, 15),
                        t("Complete a beginner tutorial on basic tools and layers", 2, 30),
                        t("Create 3 simple digital sketches", 3, 25),
                    ]),
                    g("Build core skills", "Practice essential techniques", 2, [
                        t("Practice digital linework for 20 minutes daily", 1, 20),
                        t("Learn about color theory and apply it to a piece", 2, 30),
                        t("Create a fully colored illustration", 3, 45),
                    ]),
                    g("Develop your style", "Create a mini portfolio of digital art", 3, [
                        t("Complete a 7-day art challenge (one piece per day)", 1, 30),
                        t("Create fan art or a character design", 2, 45),
                        t("Share your portfolio on social media", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Produce Your First Song",
                "Write, record, and release an original song or beat using music production software.",
                "creative", "intermediate", 60, "2 months", "music-2", "#6366F1", False,
                [
                    g("Learn your DAW", "Get comfortable with music production software", 1, [
                        t("Choose a DAW (GarageBand, FL Studio, Ableton, etc.)", 1, 15),
                        t("Complete a beginner tutorial on your DAW", 2, 45),
                        t("Create a simple 8-bar loop", 3, 30),
                    ]),
                    g("Write and arrange", "Compose your first full song", 2, [
                        t("Write lyrics or a melody", 1, 30),
                        t("Build a full song structure (intro, verse, chorus, outro)", 2, 60),
                        t("Record vocals or instruments", 3, 45),
                    ]),
                    g("Mix and release", "Polish and share your music", 3, [
                        t("Learn basic mixing (EQ, compression, levels)", 1, 30),
                        t("Master the final track", 2, 20),
                        t("Upload to SoundCloud, Spotify, or YouTube", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Build a Craft Business on Etsy",
                "Turn your creative hobby into income by opening an Etsy shop and making your first 10 sales.",
                "creative", "intermediate", 90, "3 months", "store", "#F59E0B", False,
                [
                    g("Choose your products", "Decide what to sell and validate demand", 1, [
                        t("Research trending products in your craft niche", 1, 25),
                        t("Create 5 product samples", 2, 60),
                        t("Get feedback from friends and potential buyers", 3, 20),
                    ]),
                    g("Set up your shop", "Launch your Etsy storefront", 2, [
                        t("Create your Etsy account and shop branding", 1, 30),
                        t("Photograph products with good lighting", 2, 45),
                        t("Write compelling product descriptions with keywords", 3, 30),
                    ]),
                    g("Market and sell", "Drive traffic and get your first sales", 3, [
                        t("Share your shop on social media", 1, 15),
                        t("Run a small promotion or discount for launch", 2, 10),
                        t("Reach 10 sales and collect customer reviews", 3, 15),
                    ]),
                ],
            ),
        ]

    def _social_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Overcome Social Anxiety",
                "Build confidence in social situations through gradual exposure and mindset shifts.",
                "social", "beginner", 60, "2 months", "smile", "#10B981", True,
                [
                    g("Understand your anxiety", "Identify triggers and patterns", 1, [
                        t("Journal about 3 recent situations that caused anxiety", 1, 15),
                        t("Rate your comfort level in different social settings (1-10)", 2, 10),
                        t("Learn about cognitive distortions related to social anxiety", 3, 20),
                    ]),
                    g("Small exposure challenges", "Gradually step outside your comfort zone", 2, [
                        t("Make eye contact and smile at a stranger", 1, 5),
                        t("Start a brief conversation with a cashier or barista", 2, 5),
                        t("Ask a colleague a question you already know the answer to", 3, 5),
                    ]),
                    g("Bigger social situations", "Handle groups and events with confidence", 3, [
                        t("Attend a social event and stay for at least 30 minutes", 1, 30),
                        t("Introduce yourself to someone new at the event", 2, 10),
                        t("Share a personal story in a group conversation", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Expand Your Social Circle",
                "Meet new people and build genuine friendships by putting yourself in new social environments.",
                "social", "intermediate", 90, "3 months", "users-round", "#3B82F6", True,
                [
                    g("Find your communities", "Identify where to meet like-minded people", 1, [
                        t("List 5 interests or hobbies you'd enjoy doing with others", 1, 15),
                        t("Research local clubs, meetups, or classes for those interests", 2, 20),
                        t("Sign up for 2 groups or events this month", 3, 10),
                    ]),
                    g("Show up consistently", "Become a regular face", 2, [
                        t("Attend your chosen group activity weekly for a month", 1, 30),
                        t("Remember and use people's names", 2, 5),
                        t("Suggest a coffee or hangout with someone from the group", 3, 10),
                    ]),
                    g("Deepen new friendships", "Move from acquaintance to friend", 3, [
                        t("Invite a new acquaintance to a one-on-one activity", 1, 15),
                        t("Share something personal to build trust", 2, 10),
                        t("Plan a small group outing with your new connections", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Become a Better Networker",
                "Build professional and personal connections that open doors through genuine relationship-building.",
                "social", "intermediate", 60, "2 months", "handshake", "#F59E0B", False,
                [
                    g("Develop your networking mindset", "Shift from transactional to genuine", 1, [
                        t("Write down what value you can offer others", 1, 15),
                        t("Prepare a 30-second introduction about yourself", 2, 10),
                        t("Set a goal to help one person per week with no strings attached", 3, 5),
                    ]),
                    g("Attend events strategically", "Show up where opportunities are", 2, [
                        t("Attend one networking event or industry meetup", 1, 60),
                        t("Have 3 meaningful conversations at the event", 2, 30),
                        t("Follow up with every new contact within 48 hours", 3, 15),
                    ]),
                    g("Maintain your network", "Keep connections warm over time", 3, [
                        t("Share an article or resource with a contact", 1, 10),
                        t("Schedule a quarterly check-in with 5 key contacts", 2, 15),
                        t("Make an introduction connecting two people who should know each other", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Volunteer and Give Back",
                "Find a meaningful volunteer opportunity and contribute regularly to your community.",
                "social", "beginner", 60, "2 months", "heart-hand", "#F43F5E", False,
                [
                    g("Find your cause", "Discover what matters to you", 1, [
                        t("List 3 social causes you care about", 1, 10),
                        t("Research local organizations working on those causes", 2, 20),
                        t("Contact 2 organizations to learn about volunteer opportunities", 3, 15),
                    ]),
                    g("Start volunteering", "Commit your time regularly", 2, [
                        t("Complete orientation or training at your chosen organization", 1, 30),
                        t("Volunteer for at least 2 hours per week for a month", 2, 120),
                        t("Reflect on what you're learning from the experience", 3, 10),
                    ]),
                    g("Increase your impact", "Go deeper or bring others along", 3, [
                        t("Invite a friend to volunteer with you", 1, 10),
                        t("Take on a leadership role in a project or event", 2, 30),
                        t("Share your experience on social media to inspire others", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Host Memorable Gatherings",
                "Become the person who brings people together by learning to plan and host great social events.",
                "social", "beginner", 60, "2 months", "party-popper", "#EC4899", False,
                [
                    g("Plan your first event", "Start small and intentional", 1, [
                        t("Choose a theme or activity (dinner, game night, potluck)", 1, 10),
                        t("Create a guest list of 6-8 people", 2, 10),
                        t("Send invitations at least 2 weeks in advance", 3, 10),
                    ]),
                    g("Prepare and host", "Make it a great experience", 2, [
                        t("Prepare food, drinks, and setup", 1, 60),
                        t("Create a playlist or plan conversation starters", 2, 15),
                        t("Be a great host: greet everyone, introduce people, check in", 3, 15),
                    ]),
                    g("Make it a habit", "Host regularly and improve", 3, [
                        t("Ask guests for feedback after the event", 1, 10),
                        t("Plan and host a second event with improvements", 2, 30),
                        t("Try a different format (brunch, outdoor activity, workshop)", 3, 20),
                    ]),
                ],
            ),
        ]

    def _travel_templates(self):
        g, t = self._goal, self._task
        return [
            self._tpl(
                "Plan Your Dream Vacation",
                "Research, budget, and plan an unforgettable trip to a destination you've always wanted to visit.",
                "travel", "beginner", 90, "3 months", "plane", "#0EA5E9", True,
                [
                    g("Choose and research", "Pick your destination and learn about it", 1, [
                        t("Make a shortlist of 3 dream destinations", 1, 15),
                        t("Research best time to visit, visa requirements, and safety", 2, 25),
                        t("Decide on destination and travel dates", 3, 10),
                    ]),
                    g("Budget and book", "Handle the logistics", 2, [
                        t("Set a total trip budget", 1, 15),
                        t("Book flights and accommodation", 2, 30),
                        t("Purchase travel insurance", 3, 15),
                    ]),
                    g("Plan the itinerary", "Make the most of your trip", 3, [
                        t("List must-see attractions and experiences", 1, 20),
                        t("Create a day-by-day itinerary with flexibility", 2, 30),
                        t("Pack using a checklist and prepare documents", 3, 20),
                    ]),
                ],
            ),
            self._tpl(
                "Backpack Through Europe",
                "Plan and execute a multi-city European backpacking adventure on a budget.",
                "travel", "intermediate", 120, "4 months", "backpack", "#6366F1", True,
                [
                    g("Plan the route", "Choose cities and transportation", 1, [
                        t("Select 5-8 cities to visit and map the route", 1, 30),
                        t("Research rail passes and budget flights", 2, 25),
                        t("Book hostels or budget accommodation for first 3 stops", 3, 30),
                    ]),
                    g("Prepare and budget", "Get ready for the trip", 2, [
                        t("Set a daily budget (food, transport, activities)", 1, 20),
                        t("Get a backpack and pack light (under 40L)", 2, 30),
                        t("Get necessary visas and travel cards", 3, 20),
                    ]),
                    g("On the road", "Make the most of your adventure", 3, [
                        t("Stay in each city for 2-4 days to really experience it", 1, 15),
                        t("Take a free walking tour in every city", 2, 15),
                        t("Document your trip with a travel journal or blog", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Complete a Road Trip",
                "Plan an epic road trip with scenic stops, great food, and unforgettable memories.",
                "travel", "beginner", 30, "1 month", "car", "#22C55E", False,
                [
                    g("Plan the route", "Map out your journey and stops", 1, [
                        t("Choose your start point, destination, and key stops", 1, 20),
                        t("Map the route and estimate driving time per day", 2, 15),
                        t("Research unique roadside attractions and restaurants", 3, 20),
                    ]),
                    g("Prepare the car and pack", "Get road-trip ready", 2, [
                        t("Get a vehicle checkup (oil, tires, brakes)", 1, 30),
                        t("Create a packing list (emergency kit, snacks, entertainment)", 2, 15),
                        t("Download offline maps and create a road trip playlist", 3, 15),
                    ]),
                    g("Hit the road", "Enjoy the journey", 3, [
                        t("Drive no more than 6 hours per day to enjoy stops", 1, 10),
                        t("Take photos and collect mementos at each stop", 2, 10),
                        t("Write a daily summary of highlights", 3, 10),
                    ]),
                ],
            ),
            self._tpl(
                "Travel Solo for the First Time",
                "Build confidence and independence by planning and completing your first solo trip.",
                "travel", "intermediate", 60, "2 months", "compass", "#F97316", False,
                [
                    g("Overcome the fear", "Prepare mentally for solo travel", 1, [
                        t("Read 3 solo travel blogs or watch vlogs for inspiration", 1, 20),
                        t("Choose a beginner-friendly destination", 2, 15),
                        t("Tell friends and family your plan and share your itinerary", 3, 10),
                    ]),
                    g("Plan for safety and comfort", "Handle logistics with confidence", 2, [
                        t("Book accommodation in safe, well-reviewed areas", 1, 20),
                        t("Learn 10 useful phrases if visiting a foreign country", 2, 15),
                        t("Set up a check-in system with someone at home", 3, 10),
                    ]),
                    g("Embrace the experience", "Make the most of solo travel", 3, [
                        t("Eat at a restaurant alone and enjoy it", 1, 30),
                        t("Strike up a conversation with a fellow traveler", 2, 10),
                        t("Do one thing that scares you (activity, food, exploration)", 3, 15),
                    ]),
                ],
            ),
            self._tpl(
                "Visit All 7 Continents",
                "Set a long-term travel goal to step foot on every continent, from Antarctica to Africa.",
                "travel", "advanced", 1825, "5 years", "globe", "#EF4444", False,
                [
                    g("Map your progress", "Know where you stand and plan ahead", 1, [
                        t("List continents already visited and remaining ones", 1, 10),
                        t("Research the best time and way to visit each remaining continent", 2, 30),
                        t("Prioritize your next 2 continents based on budget and interest", 3, 15),
                    ]),
                    g("Budget for the big trips", "Save strategically for expensive destinations", 2, [
                        t("Research estimated costs for Antarctica and remote destinations", 1, 25),
                        t("Set up a dedicated travel savings fund", 2, 15),
                        t("Look for deals, group tours, or off-season pricing", 3, 20),
                    ]),
                    g("Experience each continent", "Go beyond just visiting", 3, [
                        t("Spend at least 5 days per continent to truly experience it", 1, 15),
                        t("Try local food and cultural activities on each continent", 2, 15),
                        t("Take a signature photo on each continent for your collection", 3, 5),
                    ]),
                ],
            ),
        ]

    def handle(self, *args, **options):
        templates = (
            self._health_templates()
            + self._career_templates()
            + self._finance_templates()
            + self._personal_templates()
            + self._hobbies_templates()
            + self._relationships_templates()
            + self._education_templates()
            + self._creative_templates()
            + self._social_templates()
            + self._travel_templates()
        )

        created_count = 0
        updated_count = 0
        for tpl in templates:
            _, created = DreamTemplate.objects.update_or_create(
                title=tpl["title"],
                defaults=tpl,
            )
            action = "Created" if created else "Updated"
            if created:
                created_count += 1
            else:
                updated_count += 1
            self.stdout.write(f'  {action}: {tpl["title"]} ({tpl["category"]})')

        total = len(templates)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded {total} dream templates "
                f"({created_count} created, {updated_count} updated)."
            )
        )

        # Summary by category
        from collections import Counter

        cats = Counter(tpl["category"] for tpl in templates)
        self.stdout.write("\nTemplates per category:")
        for cat, count in sorted(cats.items()):
            self.stdout.write(f"  {cat}: {count}")
