import { Router } from 'express';
import { calendarController } from '../controllers/calendar.controller';

const router = Router();

router.get('/', calendarController.getCalendar);
router.get('/today', calendarController.getToday);
router.get('/week', calendarController.getWeek);

export { router as calendarRouter };
