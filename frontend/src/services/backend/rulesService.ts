import type { UnderwritingRulesDocument } from "../../types";

type JsonBody = Record<string, unknown> | unknown[];

type RulesRequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | JsonBody | null;
};

const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

const rulesBaseUrls = unique([
  configuredBaseUrl,
  configuredBaseUrl.includes("localhost")
    ? configuredBaseUrl.replace("localhost", "127.0.0.1")
    : "http://127.0.0.1:8000",
  configuredBaseUrl.includes("127.0.0.1")
    ? configuredBaseUrl.replace("127.0.0.1", "localhost")
    : "http://localhost:8000"
]);

export async function getUnderwritingRules(): Promise<UnderwritingRulesDocument> {
  return rulesApiRequest<UnderwritingRulesDocument>("/underwriting-rules");
}

export async function updateUnderwritingRules(
  document: UnderwritingRulesDocument,
  updatedBy?: string
): Promise<UnderwritingRulesDocument> {
  return rulesApiRequest<UnderwritingRulesDocument>("/underwriting-rules", {
    method: "PUT",
    body: {
      document,
      updated_by: updatedBy
    }
  });
}

async function rulesApiRequest<T>(
  path: string,
  options: RulesRequestOptions = {}
): Promise<T> {
  const errors: string[] = [];
  let backendResponseError: string | null = null;

  for (const baseUrl of rulesBaseUrls) {
    try {
      return await requestFromBaseUrl<T>(baseUrl, path, options);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(message);
      if (!message.startsWith("Could not reach backend")) {
        backendResponseError = message;
      }
    }
  }

  throw new Error(
    backendResponseError ??
      errors[0] ??
      "Could not reach underwriting rules backend."
  );
}

async function requestFromBaseUrl<T>(
  baseUrl: string,
  path: string,
  options: RulesRequestOptions
): Promise<T> {
  const headers = new Headers(options.headers);
  const body = prepareBody(options.body, headers);
  const url = `${baseUrl}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      body,
      headers
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`Could not reach backend at ${url}. ${detail}`);
  }

  const payload = await parseResponse(response);
  if (!response.ok) {
    throw new Error(
      `Backend at ${url} returned ${response.status}: ${getErrorMessage(
        payload,
        response.status
      )}`
    );
  }

  return payload as T;
}

function prepareBody(
  body: RulesRequestOptions["body"],
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
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const detail = record.detail;
    const error = record.error;

    if (typeof detail === "string") return detail;
    if (error && typeof error === "object" && "message" in error) {
      return String((error as Record<string, unknown>).message);
    }
  }

  return `Underwriting rules API request failed with status ${status}.`;
}

function unique(values: string[]) {
  return Array.from(new Set(values));
}

