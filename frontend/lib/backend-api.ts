export function getBackendApiUrl() {
  const apiUrl =
    process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  if (!apiUrl) {
    throw new Error(
      'BACKEND_API_URL or NEXT_PUBLIC_BACKEND_API_URL must be configured',
    );
  }

  return apiUrl.replace(/\/$/, '');
}
