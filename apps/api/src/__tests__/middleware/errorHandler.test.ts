import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Request, Response, NextFunction } from 'express';
import { errorHandler, AppError } from '../../middleware/errorHandler';

describe('ErrorHandler Middleware', () => {
  let mockReq: Partial<Request>;
  let mockRes: Partial<Response>;
  let mockNext: NextFunction;
  let jsonMock: ReturnType<typeof vi.fn>;
  let statusMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    jsonMock = vi.fn();
    statusMock = vi.fn().mockReturnValue({ json: jsonMock });
    mockReq = {};
    mockRes = {
      status: statusMock,
      json: jsonMock,
    };
    mockNext = vi.fn();
  });

  it('should handle AppError with correct status code', () => {
    const error = new AppError('Not found', 404);

    errorHandler(error, mockReq as Request, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(404);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        success: false,
        error: expect.objectContaining({
          message: 'Not found',
          code: 404,
        }),
      })
    );
  });

  it('should handle AppError with custom code', () => {
    const error = new AppError('Unauthorized', 401);

    errorHandler(error, mockReq as Request, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(401);
  });

  it('should handle generic Error with 500 status', () => {
    const error = new Error('Something went wrong');

    errorHandler(error, mockReq as Request, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(500);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        success: false,
        error: expect.objectContaining({
          code: 500,
        }),
      })
    );
  });

  it('should handle ZodError with 400 status', () => {
    const zodError = {
      name: 'ZodError',
      errors: [
        { path: ['title'], message: 'Required' },
        { path: ['description'], message: 'Too short' },
      ],
      message: 'Validation failed',
    };

    errorHandler(zodError as any, mockReq as Request, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(400);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        success: false,
        error: expect.objectContaining({
          message: 'Validation error',
        }),
      })
    );
  });

  it('should handle PrismaClientKnownRequestError', () => {
    const prismaError = {
      name: 'PrismaClientKnownRequestError',
      code: 'P2002',
      message: 'Unique constraint failed',
      meta: { target: ['email'] },
    };

    errorHandler(prismaError as any, mockReq as Request, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(409);
  });

  it('should handle PrismaClientKnownRequestError P2025 (not found)', () => {
    const prismaError = {
      name: 'PrismaClientKnownRequestError',
      code: 'P2025',
      message: 'Record not found',
    };

    errorHandler(prismaError as any, mockReq as Request, mockRes as Response, mockNext);

    expect(statusMock).toHaveBeenCalledWith(404);
  });
});

describe('AppError', () => {
  it('should create error with message and status code', () => {
    const error = new AppError('Test error', 400);

    expect(error.message).toBe('Test error');
    expect(error.statusCode).toBe(400);
    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(AppError);
  });

  it('should have default 500 status code', () => {
    const error = new AppError('Server error');

    expect(error.statusCode).toBe(500);
  });
});
