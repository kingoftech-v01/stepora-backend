class ApiConstants {
  // Auth (dj-rest-auth)
  static const String login = '/auth/login/';
  static const String register = '/auth/registration/';
  static const String logout = '/auth/logout/';
  static const String user = '/auth/user/';
  static const String passwordChange = '/auth/password/change/';
  static const String passwordReset = '/auth/password/reset/';

  // Dreams
  static const String dreams = '/dreams/';
  static String dreamDetail(String id) => '/dreams/$id/';
  static String dreamGoals(String id) => '/dreams/$id/goals/';
  static String dreamGeneratePlan(String id) => '/dreams/$id/generate_plan/';
  static String dreamVisionBoard(String id) => '/dreams/$id/generate_vision_board/';

  // Goals
  static const String goals = '/goals/';
  static String goalDetail(String id) => '/goals/$id/';
  static String goalTasks(String id) => '/goals/$id/tasks/';

  // Tasks
  static const String tasks = '/tasks/';
  static String taskDetail(String id) => '/tasks/$id/';
  static String taskComplete(String id) => '/tasks/$id/complete/';
  static String taskMicroStart(String id) => '/tasks/$id/two_minute_start/';

  // Conversations
  static const String conversations = '/conversations/';
  static String conversationDetail(String id) => '/conversations/$id/';
  static String conversationMessages(String id) => '/conversations/$id/messages/';

  // Calendar
  static const String calendarEvents = '/calendar/events/';
  static const String calendarOverview = '/calendar/overview/';
  static const String timeBlocks = '/calendar/time-blocks/';

  // Social
  static const String circles = '/circles/';
  static String circleDetail(String id) => '/circles/$id/';
  static const String socialFeed = '/social/feed/';
  static const String buddies = '/buddies/';

  // Leagues
  static const String leagues = '/leagues/';
  static const String leaderboard = '/leagues/leaderboard/';

  // Notifications
  static const String notifications = '/notifications/';

  // Users
  static const String userProfile = '/users/me/';
  static const String gamification = '/users/me/gamification/';
  static const String fcmToken = '/users/me/register_fcm_token/';

  // Store
  static const String storeItems = '/store/items/';
  static const String storeInventory = '/store/inventory/';
  static const String storePurchase = '/store/purchase/';

  // Subscriptions
  static const String subscriptionPlans = '/subscriptions/plans/';
  static const String subscriptionCheckout = '/subscriptions/checkout/';
  static const String subscriptionCurrent = '/subscriptions/current/';

  // WebSocket
  static String chatWs(String conversationId) => '/chat/$conversationId/';
}
