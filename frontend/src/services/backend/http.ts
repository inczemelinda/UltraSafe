import type { UserRole } from "../../types";
import { authRoleForApiPath, currentRouteAuthRole, getAccessToken } from "../authSession";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

export function resolveApiUrl(pathOrUrl?: string | null): string | undefined {
  if (!pathOrUrl) return undefined;
  try {
    return new URL(pathOrUrl).toString();
  } catch {
    const path = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
    return `${API_BASE_URL}${path}`;
  }
}

type JsonBody = Record<string, unknown> | unknown[];

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  authRole?: UserRole | "none";
  body?: BodyInit | JsonBody | null;
  skipAuth?: boolean;
};

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { authRole, skipAuth, ...requestOptions } = options;
  const headers = new Headers(requestOptions.headers);
  if (!skipAuth) applyAuthHeader(headers, path, authRole);
  const body = prepareBody(requestOptions.body, headers);
  const url = resolveApiUrl(path) ?? `${API_BASE_URL}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...requestOptions,
      body,
      headers
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`Could not reach backend at ${url}. ${detail}`);
  }

  const payload = await parseResponse(response);
  if (!response.ok) {
    throw new ApiError(getErrorMessage(payload, response.status), response.status, payload);
  }

  return payload as T;
}

export async function apiBlobRequest(
  path: string,
  options: ApiRequestOptions = {}
): Promise<{ blob: Blob; filename?: string }> {
  const { authRole, skipAuth, ...requestOptions } = options;
  const headers = new Headers(requestOptions.headers);
  if (!skipAuth) applyAuthHeader(headers, path, authRole);
  const body = prepareBody(requestOptions.body, headers);
  const url = resolveApiUrl(path) ?? `${API_BASE_URL}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...requestOptions,
      body,
      headers
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`Could not reach backend at ${url}. ${detail}`);
  }

  if (!response.ok) {
    const payload = await parseResponse(response);
    throw new ApiError(getErrorMessage(payload, response.status), response.status, payload);
  }

  return {
    blob: await response.blob(),
    filename: filenameFromContentDisposition(response.headers.get("Content-Disposition"))
  };
}

function applyAuthHeader(
  headers: Headers,
  path: string,
  requestedRole?: UserRole | "none"
) {
  if (requestedRole === "none") return;
  const inferredRole = requestedRole ?? authRoleForApiPath(path);
  if (inferredRole === "none") return;
  const role = inferredRole ?? currentRouteAuthRole();
  if (!role) return;
  const token = getAccessToken(role);
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
}

function filenameFromContentDisposition(value: string | null) {
  if (!value) return undefined;
  const match = /filename="?([^";]+)"?/i.exec(value);
  return match?.[1];
}

function prepareBody(
  body: ApiRequestOptions["body"],
  headers: Headers
): BodyInit | null | undefined {
  if (body == null || typeof body === "string" || body instanceof FormData) {
    return body as BodyInit | null | undefined;
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return JSON.stringify(body);
}

async function parseResponse(response: Response) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function getErrorMessage(payload: unknown, status: number) {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const detail = record.detail;
    const error = record.error;

    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "error" in detail) {
      return String((detail as Record<string, unknown>).error);
    }
    if (error && typeof error === "object" && "message" in error) {
      const specific = specificBackendErrorMessage(error as Record<string, unknown>);
      if (specific) return specific;
      return String((error as Record<string, unknown>).message);
    }
  }

  return `API request failed with status ${status}.`;
}

function specificBackendErrorMessage(error: Record<string, unknown>) {
  const validation = error.validation;
  if (validation && typeof validation === "object") {
    const blockingErrors = (validation as Record<string, unknown>).blocking_errors;
    const firstMessage = firstIssueMessage(blockingErrors);
    if (firstMessage) return firstMessage;
  }

  const firstBlockingMessage = firstIssueMessage(error.blocking_errors);
  if (firstBlockingMessage) return firstBlockingMessage;

  const firstModuleMessage = firstIssueMessage(error.module_results);
  if (firstModuleMessage) return firstModuleMessage;

  return undefined;
}

function firstIssueMessage(value: unknown) {
  if (!Array.isArray(value)) return undefined;
  const first = value.find((item) => item && typeof item === "object");
  if (!first) return undefined;
  const record = first as Record<string, unknown>;
  return typeof record.message === "string"
    ? record.message
    : typeof record.summary === "string"
      ? record.summary
      : undefined;
}

