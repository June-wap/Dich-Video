import { Request, Response, NextFunction } from 'express';
import { getAdminApiKey } from '../config';

/**
 * Middleware kiểm tra Admin Authentication.
 * Yêu cầu request mang header X-Admin-Key hoặc query adminKey khớp với ADMIN_API_KEY.
 */
export function requireAdminAuth(req: Request, res: Response, next: NextFunction): void {
  const providedKey = req.headers['x-admin-key'] || req.query.adminKey;
  const expectedKey = getAdminApiKey();

  if (!providedKey || typeof providedKey !== 'string') {
    res.status(401).json({
      ok: false,
      errorCode: 'UNAUTHORIZED',
      message: 'Thiếu mã xác thực quản trị (X-Admin-Key header required).',
    });
    return;
  }

  // Chống timing attack bằng crypto.timingSafeEqual nếu độ dài bằng nhau
  const crypto = require('crypto');
  const providedBuf = Buffer.from(providedKey);
  const expectedBuf = Buffer.from(expectedKey);

  if (providedBuf.length !== expectedBuf.length || !crypto.timingSafeEqual(providedBuf, expectedBuf)) {
    res.status(403).json({
      ok: false,
      errorCode: 'UNAUTHORIZED',
      message: 'Mã xác thực quản trị không chính xác.',
    });
    return;
  }

  next();
}
