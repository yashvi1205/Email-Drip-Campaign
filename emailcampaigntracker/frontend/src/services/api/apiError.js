export class ApiError extends Error {
  constructor({ message, status, requestId, cause } = {}) {
    super(message || 'Request failed');
    this.name = 'ApiError';
    this.status = status;
    this.requestId = requestId;
    this.cause = cause;
  }
}

export function extractRequestId(error) {
  // Backend error envelope:
  // { error: { code, message, request_id } }
  const bodyReqId = error?.response?.data?.error?.request_id;
  if (bodyReqId) return bodyReqId;
  // Middleware header:
  const headerReqId = error?.response?.headers?.['x-request-id'] || error?.response?.headers?.['X-Request-ID'];
  return headerReqId || undefined;
}

export function fromAxiosError(error) {
  const status = error?.response?.status;
  const message =
    error?.response?.data?.error?.message ||
    error?.response?.data?.message ||
    error?.message ||
    'Request failed';
  const requestId = extractRequestId(error);
  return new ApiError({ message, status, requestId, cause: error });
}

