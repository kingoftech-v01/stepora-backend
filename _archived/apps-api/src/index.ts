import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';
import 'dotenv/config';
import { initializeSentry, Sentry } from './config/sentry';

import { authRouter } from './routes/auth';
import { dreamsRouter } from './routes/dreams';
import { goalsRouter } from './routes/goals';
import { tasksRouter } from './routes/tasks';
import { conversationsRouter } from './routes/conversations';
import { calendarRouter } from './routes/calendar';
import { notificationsRouter } from './routes/notifications';
import { usersRouter } from './routes/users';
import { microStartRouter } from './routes/microStart';
import { rescueModeRouter } from './routes/rescueMode';
import { gamificationRouter } from './routes/gamification';
import { socialRouter } from './routes/social';
import { buddyRouter } from './routes/buddy';
import { circleRouter } from './routes/circle';
import { healthRouter } from './routes/health';
import { errorHandler } from './middleware/errorHandler';
import { authMiddleware } from './middleware/auth';
import { initializeFirebase } from './config/firebase';
import { initializeNotificationWorker } from './workers/notificationWorker';
import { initializeRescueModeWorker } from './workers/rescueModeWorker';

// Initialize Sentry first
initializeSentry();

const app = express();
const httpServer = createServer(app);
const io = new SocketServer(httpServer, {
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
    methods: ['GET', 'POST'],
  },
});

// Initialize Firebase Admin
initializeFirebase();

// Initialize workers
initializeNotificationWorker();
initializeRescueModeWorker();

// Sentry request handler must be first
if (process.env.SENTRY_DSN) {
  app.use(Sentry.Handlers.requestHandler());
  app.use(Sentry.Handlers.tracingHandler());
}

// Middleware
app.use(helmet());
app.use(cors({ origin: process.env.CORS_ORIGIN || '*' }));
app.use(express.json());

// Health and metrics routes (public)
app.use('/', healthRouter);

// Public routes
app.use('/api/auth', authRouter);

// Protected routes
app.use('/api/users', authMiddleware, usersRouter);
app.use('/api/dreams', authMiddleware, dreamsRouter);
app.use('/api/goals', authMiddleware, goalsRouter);
app.use('/api/tasks', authMiddleware, tasksRouter);
app.use('/api/conversations', authMiddleware, conversationsRouter);
app.use('/api/calendar', authMiddleware, calendarRouter);
app.use('/api/notifications', authMiddleware, notificationsRouter);
app.use('/api/micro-start', authMiddleware, microStartRouter);
app.use('/api/rescue-mode', authMiddleware, rescueModeRouter);
app.use('/api/gamification', authMiddleware, gamificationRouter);
app.use('/api/social', authMiddleware, socialRouter);
app.use('/api/buddies', authMiddleware, buddyRouter);
app.use('/api/circles', authMiddleware, circleRouter);

// WebSocket for real-time chat
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);

  socket.on('join-conversation', (conversationId: string) => {
    socket.join(`conversation:${conversationId}`);
  });

  socket.on('leave-conversation', (conversationId: string) => {
    socket.leave(`conversation:${conversationId}`);
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

// Sentry error handler (must be before other error handlers)
if (process.env.SENTRY_DSN) {
  app.use(Sentry.Handlers.errorHandler());
}

// Error handling
app.use(errorHandler);

// Start server
const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, () => {
  console.log(`🚀 DreamPlanner API running on port ${PORT}`);
  console.log(`📊 Environment: ${process.env.NODE_ENV || 'development'}`);
});

export { io };
