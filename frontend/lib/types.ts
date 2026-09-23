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
  source_url?: string;
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
};
