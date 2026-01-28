import { beforeAll, afterAll, afterEach } from 'vitest';
import { prisma } from '../src/utils/prisma';

beforeAll(async () => {
  // Setup test database
  process.env.NODE_ENV = 'test';
  process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgresql://test:test@localhost:5432/dreamplanner_test';
});

afterEach(async () => {
  // Clean up database after each test
  const tableNames = await prisma.$queryRaw<Array<{ tablename: string }>>`
    SELECT tablename FROM pg_tables WHERE schemaname='public'
  `;

  for (const { tablename } of tableNames) {
    if (tablename !== '_prisma_migrations') {
      try {
        await prisma.$executeRawUnsafe(`TRUNCATE TABLE "public"."${tablename}" CASCADE;`);
      } catch (error) {
        console.log(`Error truncating ${tablename}:`, error);
      }
    }
  }
});

afterAll(async () => {
  await prisma.$disconnect();
});
