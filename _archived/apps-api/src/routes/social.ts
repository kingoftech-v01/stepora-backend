import { Router } from 'express';
import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { asyncHandler } from '../middleware/errorHandler';
import { socialService } from '../services/social.service';
import { success } from '../utils/response';
import { z } from 'zod';
import { validate } from '../middleware/validation';

const router = Router();

const sendFriendRequestSchema = z.object({
  body: z.object({
    targetUserId: z.string().uuid(),
  }),
});

const friendRequestActionSchema = z.object({
  params: z.object({
    requestId: z.string().uuid(),
  }),
});

const removeFriendSchema = z.object({
  params: z.object({
    friendId: z.string().uuid(),
  }),
});

const followUserSchema = z.object({
  body: z.object({
    targetUserId: z.string().uuid(),
  }),
});

const unfollowUserSchema = z.object({
  params: z.object({
    userId: z.string().uuid(),
  }),
});

const searchUsersSchema = z.object({
  query: z.object({
    q: z.string().min(1),
    limit: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 20)),
  }),
});

const feedQuerySchema = z.object({
  query: z.object({
    limit: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 50)),
  }),
});

// ===== FRIENDSHIPS =====

// Send friend request
router.post(
  '/friends/request',
  validate(sendFriendRequestSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { targetUserId } = req.body;
    const userId = req.user!.id;

    await socialService.sendFriendRequest(userId, targetUserId);

    return success(res, null, 'Demande d\'ami envoyée');
  })
);

// Accept friend request
router.post(
  '/friends/accept/:requestId',
  validate(friendRequestActionSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { requestId } = req.params;
    const userId = req.user!.id;

    await socialService.acceptFriendRequest(userId, requestId);

    return success(res, null, 'Demande d\'ami acceptée');
  })
);

// Reject friend request
router.post(
  '/friends/reject/:requestId',
  validate(friendRequestActionSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { requestId } = req.params;
    const userId = req.user!.id;

    await socialService.rejectFriendRequest(userId, requestId);

    return success(res, null, 'Demande d\'ami rejetée');
  })
);

// Remove friend
router.delete(
  '/friends/:friendId',
  validate(removeFriendSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { friendId } = req.params;
    const userId = req.user!.id;

    await socialService.removeFriend(userId, friendId);

    return success(res, null, 'Ami retiré');
  })
);

// Get friends list
router.get(
  '/friends',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const friends = await socialService.getFriends(userId);

    return success(res, { friends });
  })
);

// Get pending friend requests
router.get(
  '/friends/requests/pending',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const requests = await socialService.getPendingRequests(userId);

    return success(res, { requests });
  })
);

// ===== FOLLOWS =====

// Follow user
router.post(
  '/follow',
  validate(followUserSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { targetUserId } = req.body;
    const userId = req.user!.id;

    await socialService.followUser(userId, targetUserId);

    return success(res, null, 'Utilisateur suivi');
  })
);

// Unfollow user
router.delete(
  '/follow/:userId',
  validate(unfollowUserSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { userId: targetUserId } = req.params;
    const userId = req.user!.id;

    await socialService.unfollowUser(userId, targetUserId);

    return success(res, null, 'Utilisateur non suivi');
  })
);

// Get followers
router.get(
  '/followers',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const followers = await socialService.getFollowers(userId);

    return success(res, { followers });
  })
);

// Get following
router.get(
  '/following',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const following = await socialService.getFollowing(userId);

    return success(res, { following });
  })
);

// ===== SEARCH =====

// Search users
router.get(
  '/users/search',
  validate(searchUsersSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { q: searchQuery, limit } = req.query as { q: string; limit: number };

    const users = await socialService.searchUsers(searchQuery, userId, limit);

    return success(res, { users });
  })
);

// ===== ACTIVITY FEED =====

// Get friends activity feed
router.get(
  '/feed/friends',
  validate(feedQuerySchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const limit = parseInt(req.query.limit as string) || 50;

    const activities = await socialService.getFriendsFeed(userId, limit);

    return success(res, { activities });
  })
);

export { router as socialRouter };
