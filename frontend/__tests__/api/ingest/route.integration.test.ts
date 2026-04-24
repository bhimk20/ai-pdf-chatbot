import { POST } from '../../../app/api/ingest/route';

describe('POST /api/ingest', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it('proxies multipart uploads to the FastAPI backend', async () => {
    const backendResponse = {
      message: 'Documents ingested successfully',
      threadId: 'test-thread-id',
    };

    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: jest.fn().mockResolvedValue(backendResponse),
    } as unknown as Response);

    const formData = new FormData();
    formData.append(
      'files',
      new File(['%PDF-1.7'], 'sample.pdf', { type: 'application/pdf' }),
    );

    const request = new Request('http://localhost:3000/api/ingest', {
      method: 'POST',
      body: formData,
    });

    const response = await POST(request as any);
    const data = await response.json();

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/ingest',
      expect.objectContaining({
        method: 'POST',
        body: formData,
      }),
    );
    expect(response.status).toBe(200);
    expect(data).toEqual(backendResponse);
  });
});
