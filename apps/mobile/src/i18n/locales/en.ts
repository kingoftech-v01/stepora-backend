/**
 * English translations (master file).
 * All translation keys MUST be defined here first.
 */
const en = {
  // Navigation tabs
  nav: {
    home: 'Home',
    calendar: 'Calendar',
    chat: 'Chat',
    social: 'Social',
    profile: 'Profile',
  },

  // Common UI strings
  common: {
    loading: 'Loading...',
    error: 'An error occurred',
    retry: 'Retry',
    cancel: 'Cancel',
    save: 'Save',
    delete: 'Delete',
    confirm: 'Confirm',
    back: 'Back',
    next: 'Next',
    done: 'Done',
    search: 'Search',
    filter: 'Filter',
    empty: 'Nothing here yet',
    ok: 'OK',
    yes: 'Yes',
    no: 'No',
    edit: 'Edit',
    close: 'Close',
    seeAll: 'See all',
    noResults: 'No results found',
  },

  // Authentication
  auth: {
    login: 'Log in',
    register: 'Create account',
    email: 'Email',
    password: 'Password',
    forgotPassword: 'Forgot password?',
    logout: 'Log out',
    loginError: 'Login Error',
    checkCredentials: 'Please check your credentials',
    emailRequired: 'Email and password are required',
    loginFailed: 'Login failed',
    subtitle: 'Turn your dreams into reality',
  },

  // Dreams
  dreams: {
    myDreams: 'My Dreams',
    createDream: 'New dream',
    dreamTitle: 'Dream title',
    dreamDescription: 'Description',
    targetDate: 'Target date',
    progress: 'Progress',
    goals: 'Goals',
    tasks: 'Tasks',
    priority: 'Priority',
    category: 'Category',
    noDreams: 'No dreams yet',
    noDreamsSubtext: 'Start by creating your first dream',
    todayTasks: '{{count}} task today',
    todayTasksPlural: '{{count}} tasks today',
    active: 'Active',
    completed: 'Completed',
    paused: 'Paused',
    archived: 'Archived',
  },

  // Chat / AI Assistant
  chat: {
    aiAssistant: 'DreamPlanner',
    assistantSubtitle: 'Your assistant to achieve your dreams',
    typeMessage: 'Type a message...',
    send: 'Send',
    newConversation: 'New conversation',
    thinking: 'DreamPlanner is thinking...',
    errorMessage: "Sorry, I couldn't process your request. Please try again in a moment.",
    welcomeMessage:
      "Hello! I'm DreamPlanner, your personal assistant to turn your dreams into reality.\n\nTell me what you'd like to achieve. What's your next big goal?",
  },

  // Calendar
  calendar: {
    today: 'Today',
    week: 'Week',
    month: 'Month',
    scheduledTasks: 'Scheduled tasks',
    noTasks: 'No tasks scheduled',
    addTask: 'Add a task',
    dueDate: 'Due date',
    time: 'Time',
    duration: 'Duration',
  },

  // Social
  social: {
    friends: 'Friends',
    requests: 'Requests',
    activity: 'Activity',
    circles: 'Circles',
    buddy: 'Dream Buddy',
    search: 'Search people',
    noFriends: 'No friends yet',
    noActivity: 'No recent activity',
    joinCircle: 'Join a circle',
    createCircle: 'Create a circle',
    members: 'Members',
    challenges: 'Challenges',
  },

  // Profile
  profile: {
    settings: 'Settings',
    subscription: 'Subscription',
    store: 'Store',
    notifications: 'Notifications',
    appearance: 'Appearance',
    language: 'Language',
    workSchedule: 'Work schedule',
    goPremium: 'Go Premium',
    badges: 'Badges',
    dreamsInProgress: 'Dreams\nin progress',
    tasksCompleted: 'Tasks\ncompleted',
    streakDays: 'Day\nstreak',
    level: 'Level',
    version: 'DreamPlanner v1.0.0',
    light: 'Light',
  },

  // Subscriptions
  subscriptions: {
    free: 'Free',
    premium: 'Premium',
    pro: 'Pro',
    upgrade: 'Upgrade',
    currentPlan: 'Current plan',
    monthlyPrice: 'Monthly price',
    yearlyPrice: 'Yearly price',
    features: 'Features',
    subscribe: 'Subscribe',
    restorePurchases: 'Restore purchases',
    cancelAnytime: 'Cancel anytime',
    perMonth: '/month',
    perYear: '/year',
  },

  // Store
  store: {
    categories: 'Categories',
    items: 'Items',
    purchase: 'Purchase',
    inventory: 'Inventory',
    equip: 'Equip',
    unequip: 'Unequip',
    owned: 'Owned',
    price: 'Price',
    preview: 'Preview',
    buyNow: 'Buy now',
    skins: 'Skins',
    themes: 'Themes',
    avatars: 'Avatars',
    effects: 'Effects',
  },

  // Leagues
  leagues: {
    league: 'League',
    rank: 'Rank',
    score: 'Score',
    season: 'Season',
    standings: 'Standings',
    promote: 'Promote',
    demote: 'Demote',
    weeklyScore: 'Weekly score',
    topPlayers: 'Top players',
    yourRank: 'Your rank',
    leaderboard: 'Leaderboard',
    bronze: 'Bronze',
    silver: 'Silver',
    gold: 'Gold',
    platinum: 'Platinum',
    diamond: 'Diamond',
    master: 'Master',
    legend: 'Legend',
  },

  // Vision Board
  visionBoard: {
    generate: 'Generate',
    visionBoards: 'Vision Boards',
    proRequired: 'Pro required',
    createBoard: 'Create a vision board',
    generatingImage: 'Generating image...',
    boardTitle: 'Board title',
  },
} as const;

export type TranslationKeys = typeof en;
export default en;
