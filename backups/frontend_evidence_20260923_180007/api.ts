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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

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
    throw new Error(
      payload?.detail ??
        "The service is temporarily unavailable. Please try again.",
    );
  }

  return payload as AskResponse;
}
