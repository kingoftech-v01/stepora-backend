import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';
import 'dotenv/config';

import { authRouter } from './routes/auth';
import { dreamsRouter } from './routes/dreams';
import { goalsRouter } from './routes/goals';
import { tasksRouter } from './routes/tasks';
import { conversationsRouter } from './routes/conversations';
import { calendarRouter } from './routes/calendar';
import { notificationsRouter } from './routes/notifications';
import { usersRouter } from './routes/users';
import { errorHandler } from './middleware/errorHandler';
import { authMiddleware } from './middleware/auth';
import { initializeFirebase } from './config/firebase';
import { initializeNotificationWorker } from './workers/notificationWorker';

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

// Initialize notification worker
initializeNotificationWorker();

// Middleware
app.use(helmet());
app.use(cors({ origin: process.env.CORS_ORIGIN || '*' }));
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

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

// Error handling
app.use(errorHandler);

// Start server
const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, () => {
  console.log(`🚀 DreamPlanner API running on port ${PORT}`);
  console.log(`📊 Environment: ${process.env.NODE_ENV || 'development'}`);
});

export { io };
