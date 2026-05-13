import { AxiosError } from 'axios';

export class ApiError extends Error {
  status?: number;
  code: string = 'UNKNOWN_ERROR';
  requestId?: string;
  cause?: AxiosError;

  constructor({
    message = 'Request failed',
    status,
    code = 'UNKNOWN_ERROR',
    requestId,
    cause,
  }: {
    message?: string;
    status?: number;
    code?: string;
    requestId?: string;
    cause?: AxiosError;
  } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.cause = cause;
  }
}

export function extractRequestId(error: AxiosError): string | undefined {
  const bodyReqId = (error?.response?.data as any)?.error?.request_id;
  if (bodyReqId) return bodyReqId;
  const headerReqId =
    error?.response?.headers['x-request-id'] ||
    error?.response?.headers['X-Request-ID'];
  return headerReqId;
}

export function fromAxiosError(error: AxiosError): ApiError {
  const status = error?.response?.status;
  const message =
    (error?.response?.data as any)?.error?.message ||
    (error?.response?.data as any)?.message ||
    error?.message ||
    'Request failed';
  const code =
    (error?.response?.data as any)?.error?.code || 'UNKNOWN_ERROR';
  const requestId = extractRequestId(error);

  return new ApiError({
    message,
    status,
    code,
    requestId,
    cause: error,
  });
}
