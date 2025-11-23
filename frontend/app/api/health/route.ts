/**
 * Next.js Health Check Endpoint
 */

import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'nextjs',
    timestamp: new Date().toISOString(),
  });
}
