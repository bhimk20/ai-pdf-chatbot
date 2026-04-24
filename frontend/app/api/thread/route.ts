import { NextResponse } from 'next/server';
import { getBackendApiUrl } from '@/lib/backend-api';

export async function GET() {
  try {
    const response = await fetch(`${getBackendApiUrl()}/threads`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      cache: 'no-store',
    });

    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : { error: await response.text() };
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Thread list route error:', error);
    return NextResponse.json(
      { error: 'Failed to list threads' },
      { status: 500 },
    );
  }
}

export async function POST() {
  try {
    const response = await fetch(`${getBackendApiUrl()}/threads`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
      },
      cache: 'no-store',
    });

    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : { error: await response.text() };
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Thread route error:', error);
    return NextResponse.json(
      { error: 'Failed to create thread' },
      { status: 500 },
    );
  }
}
