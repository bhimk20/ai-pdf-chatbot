import { NextResponse } from 'next/server';
import { getBackendApiUrl } from '@/lib/backend-api';

export async function GET(
  _request: Request,
  context: { params: { threadId: string } },
) {
  try {
    const response = await fetch(
      `${getBackendApiUrl()}/threads/${context.params.threadId}`,
      {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
        cache: 'no-store',
      },
    );

    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : { error: await response.text() };
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Thread fetch route error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch thread' },
      { status: 500 },
    );
  }
}

export async function DELETE(
  _request: Request,
  context: { params: { threadId: string } },
) {
  try {
    const response = await fetch(
      `${getBackendApiUrl()}/threads/${context.params.threadId}`,
      {
        method: 'DELETE',
        headers: {
          Accept: 'application/json',
        },
        cache: 'no-store',
      },
    );

    if (response.status === 204) {
      return new Response(null, { status: 204 });
    }

    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : { error: await response.text() };
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Thread delete route error:', error);
    return NextResponse.json(
      { error: 'Failed to delete thread' },
      { status: 500 },
    );
  }
}
