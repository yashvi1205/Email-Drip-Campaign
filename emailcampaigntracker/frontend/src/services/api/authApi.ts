import { httpClient } from './httpClient';
import { User } from '@types/index';
import { setAuthToken, setRefreshToken } from './apiConfig';

export type LoginRequest = {
  username: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  user: User;
};

export type RegisterRequest = {
  username: string;
  email: string;
  password: string;
};

export type RegisterResponse = {
  user: User;
  access_token: string;
  refresh_token: string;
};

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const response = await httpClient.post<LoginResponse>('/auth/login', credentials);
  const { access_token, refresh_token } = response.data;
  setAuthToken(access_token);
  setRefreshToken(refresh_token);
  return response.data;
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  const response = await httpClient.post<RegisterResponse>(
    '/auth/register',
    data
  );
  const { access_token, refresh_token } = response.data;
  setAuthToken(access_token);
  setRefreshToken(refresh_token);
  return response.data;
}

export async function getCurrentUser(): Promise<User> {
  const response = await httpClient.get<User>('/auth/me');
  return response.data;
}

export async function refreshToken(): Promise<LoginResponse> {
  const response = await httpClient.post<LoginResponse>('/auth/refresh', {});
  const { access_token, refresh_token } = response.data;
  setAuthToken(access_token);
  setRefreshToken(refresh_token);
  return response.data;
}
