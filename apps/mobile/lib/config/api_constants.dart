class ApiConstants {
  // Auth (dj-rest-auth)
  static const String login = '/auth/login/';
  static const String register = '/auth/registration/';
  static const String logout = '/auth/logout/';
  static const String user = '/auth/user/';
  static const String passwordChange = '/auth/password/change/';
  static const String passwordReset = '/auth/password/reset/';
  // Social auth (dj-rest-auth social)
  static const String googleLogin = '/auth/google/';
  static const String appleLogin = '/auth/apple/';

  // Dreams
  static const String dreams = '/dreams/';
  static String dreamDetail(String id) => '/dreams/$id/';
  static String dreamGoals(String id) => '/dreams/$id/goals/';
  static String dreamGeneratePlan(String id) => '/dreams/$id/generate_plan/';
  static String dreamVisionBoard(String id) => '/dreams/$id/generate_vision_board/';
  static String dreamDuplicate(String id) => '/dreams/$id/duplicate/';
  static String dreamShare(String id) => '/dreams/$id/share/';
  static String dreamObstacles(String id) => '/dreams/$id/obstacles/';
  static String dreamExportPdf(String id) => '/dreams/$id/export-pdf/';
  static String dreamCollaborators(String id) => '/dreams/$id/collaborators/';
  static const String dreamTemplates = '/dreams/templates/';
  static const String dreamsSharedWithMe = '/dreams/shared-with-me/';

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
  static String conversationSendMessage(String id) => '/conversations/$id/send_message/';
  static String conversationSendVoice(String id) => '/conversations/$id/send-voice/';
  static String conversationSendImage(String id) => '/conversations/$id/send-image/';
  static String conversationExport(String id) => '/conversations/$id/export/';
  static const String conversationTemplates = '/conversation-templates/';

  // Calendar
  static const String calendarEvents = '/calendar/events/';
  static String calendarEventDetail(String id) => '/calendar/events/$id/';
  static String calendarReschedule(String id) => '/calendar/events/$id/reschedule/';
  static const String calendarOverview = '/calendar/overview/';
  static const String timeBlocks = '/calendar/timeblocks/';
  static const String autoSchedule = '/calendar/auto-schedule/';
  static const String suggestTimeSlots = '/calendar/suggest-time-slots/';
  // Google Calendar
  static const String googleCalendarAuth = '/calendar/google/auth/';
  static const String googleCalendarCallback = '/calendar/google/callback/';
  static const String googleCalendarSync = '/calendar/google/sync/';
  static const String googleCalendarDisconnect = '/calendar/google/disconnect/';

  // Social
  static const String circles = '/circles/';
  static String circleDetail(String id) => '/circles/$id/';
  static String circlePosts(String id) => '/circles/$id/posts/';
  static String circleJoin(String id) => '/circles/$id/join/';
  static String circleLeave(String id) => '/circles/$id/leave/';
  static String circleInvite(String id) => '/circles/$id/invite/';
  static String circleInviteLink(String id) => '/circles/$id/invite-link/';
  static String joinByInviteCode(String code) => '/circles/join/$code/';
  static const String myInvitations = '/circles/my-invitations/';
  static const String socialFeed = '/social/feed/';
  static const String socialFriends = '/social/friends/';
  static const String socialFriendsPending = '/social/friends/requests/pending/';
  static const String socialFriendsSent = '/social/friends/requests/sent/';
  static const String socialFriendRequest = '/social/friends/request/';
  static String socialFriendAccept(String id) => '/social/friends/accept/$id/';
  static String socialFriendReject(String id) => '/social/friends/reject/$id/';
  static String socialFriendRemove(String id) => '/social/friends/remove/$id/';
  static const String socialFollow = '/social/follow/';
  static String socialUnfollow(String id) => '/social/unfollow/$id/';
  static const String socialSearch = '/social/search/';
  static const String socialBlock = '/social/block/';
  static String socialUnblock(String id) => '/social/unblock/$id/';
  static String socialMutualFriends(String id) => '/social/friends/mutual/$id/';
  static const String followSuggestions = '/social/follow-suggestions/';
  static const String socialReport = '/social/report/';

  // Buddies
  static const String buddies = '/buddies/';
  static String buddyDetail(String id) => '/buddies/$id/';
  static String buddyEncourage(String id) => '/buddies/$id/encourage/';
  static String buddyAccept(String id) => '/buddies/$id/accept/';
  static String buddyReject(String id) => '/buddies/$id/reject/';
  static const String buddyHistory = '/buddies/history/';

  // Leagues
  static const String leagues = '/leagues/';
  static const String leaderboard = '/leagues/leaderboard/';
  static const String seasons = '/leagues/seasons/';

  // Notifications
  static const String notifications = '/notifications/';
  static String notificationDetail(String id) => '/notifications/$id/';
  static String notificationRead(String id) => '/notifications/$id/read/';
  static const String notificationsMarkAllRead = '/notifications/mark-all-read/';
  static const String notificationsUnreadCount = '/notifications/unread-count/';

  // Users
  static const String userProfile = '/users/me/';
  static const String gamification = '/users/me/gamification/';
  static const String fcmToken = '/users/me/register_fcm_token/';
  static const String userUploadAvatar = '/users/me/upload-avatar/';
  static const String userExportData = '/users/me/export-data/';
  static const String userDeleteAccount = '/users/me/delete-account/';
  static const String userChangeEmail = '/users/me/change-email/';
  static const String userNotificationPrefs = '/users/me/notification-preferences/';
  static const String userStats = '/users/me/stats/';
  static const String userUpdateProfile = '/users/me/update_profile/';
  // 2FA
  static const String twoFactorSetup = '/users/2fa/setup/';
  static const String twoFactorVerify = '/users/2fa/verify/';
  static const String twoFactorDisable = '/users/2fa/disable/';
  static const String twoFactorStatus = '/users/2fa/status/';
  static const String twoFactorBackupCodes = '/users/2fa/backup-codes/';

  // Store
  static const String storeItems = '/store/items/';
  static const String storeCategories = '/store/categories/';
  static const String storeFeatured = '/store/items/featured/';
  static const String storeInventory = '/store/inventory/';
  static String storeInventoryEquip(String id) => '/store/inventory/$id/equip/';
  static const String storeInventoryHistory = '/store/inventory/history/';
  static const String storePurchase = '/store/purchase/';
  static const String storePurchaseConfirm = '/store/purchase/confirm/';
  static const String storePurchaseXp = '/store/purchase/xp/';
  static const String storeWishlist = '/store/wishlist/';
  // Gifting
  static const String storeGiftSend = '/store/gifts/send/';
  static String storeGiftClaim(String id) => '/store/gifts/$id/claim/';
  static const String storeGifts = '/store/gifts/';
  // Refunds
  static const String storeRefunds = '/store/refunds/';

  // Subscriptions
  static const String subscriptionPlans = '/subscriptions/plans/';
  static const String subscriptionCheckout = '/subscriptions/checkout/';
  static const String subscriptionCurrent = '/subscriptions/current/';
  static const String subscriptionCancel = '/subscriptions/cancel/';
  static const String subscriptionReactivate = '/subscriptions/reactivate/';
  static const String subscriptionPortal = '/subscriptions/portal/';
  static const String subscriptionSync = '/subscriptions/sync/';
  static const String subscriptionInvoices = '/subscriptions/invoices/';

  // WebSocket
  static String chatWs(String conversationId) => '/conversations/$conversationId/';
  static String buddyChatWs(String conversationId) => '/buddy-chat/$conversationId/';
}
