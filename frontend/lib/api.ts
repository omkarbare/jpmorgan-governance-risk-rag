export type Citation = {
  citation_index: number;
  score: number;
  chunk_id: string;
  doc_id: string;
  doc_title: string;
  doc_type: string;
  section_path: string;
  item_number: string;
  page_pdf: number | null;
  page_printed: number | null;
  content_type: string;
  table_caption: string | null;
  source_file: string;
  source_url: string;
};

export type AskResponse = {
  request_id: string;
  answer: string;
  citations: Citation[];
  retrieval_count: number;
  citation_count: number;
  model: string;
  collection: string;
  latency_ms: number;
  guardrail_status: "passed" | "blocked";
  guardrail_reason?: string | null;
};

export type ApiRequestError = Error & {
  status?: number;
  providerLimit?: boolean;
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

function isProviderLimitMessage(value: unknown): boolean {
  const message = String(value ?? "").toLowerCase();

  return [
    "rate limit",
    "rate_limit",
    "quota",
    "too many requests",
    "limit exceeded",
    "billing",
    "insufficient_quota",
    "api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "provider",
    "temporarily unavailable",
  ].some((phrase) => message.includes(phrase));
}

export async function askRag(
  query: string,
  groqApiKey?: string,
  openaiApiKey?: string,
): Promise<AskResponse> {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(groqApiKey ? { "x-groq-api-key": groqApiKey } : {}),
      ...(openaiApiKey ? { "x-openai-api-key": openaiApiKey } : {}),
    },
    body: JSON.stringify({
      query,
      top_k: 5,
    }),
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      payload?.detail ??
      "The service is temporarily unavailable. Please try again.";

    const error = new Error(detail) as ApiRequestError;
    error.status = response.status;
    error.providerLimit =
      response.status === 401 ||
      response.status === 403 ||
      response.status === 429 ||
      isProviderLimitMessage(detail);

    throw error;
  }

  return payload as AskResponse;
}
