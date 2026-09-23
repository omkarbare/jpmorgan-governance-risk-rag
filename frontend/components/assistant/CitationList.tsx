"use client";

import { useState } from "react";
import type { AskResponse, Citation } from "@/lib/api";

type CitationListProps = {
  citations: Citation[];
  response: AskResponse;
};

function displayValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  return String(value);
}

function CitationCard({
  citation,
  response,
}: {
  citation: Citation;
  response: AskResponse;
}) {
  const [isOpen, setIsOpen] = useState(false);

  const page = citation.page_printed ?? citation.page_pdf;

  const location = [
    citation.section_path,
    citation.item_number,
    page ? `Page ${page}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const latencySeconds = (response.latency_ms / 1000).toFixed(2);

  return (
    <article className="citation-card-rich">
      <div className="citation-card-top">
        <span className="citation-number">[{citation.citation_index}]</span>

        <div className="citation-overview">
          <p className="citation-document">
            {citation.doc_title || citation.source_file || "Source document"}
          </p>

          <p className="citation-location">
            {location || "Document excerpt"}
          </p>
        </div>

        <span className="citation-score">
          Score {citation.score.toFixed(4)}
        </span>
      </div>

      <div className="citation-summary-grid">
        <span>
          <strong>Source</strong>
          {displayValue(citation.source_file)}
        </span>

        <span>
          <strong>Document type</strong>
          {displayValue(citation.doc_type)}
        </span>

        <span>
          <strong>Content</strong>
          {displayValue(citation.content_type)}
        </span>

        <span>
          <strong>Latency</strong>
          {latencySeconds} seconds
        </span>
      </div>

      <button
        className="citation-details-toggle"
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        aria-expanded={isOpen}
      >
        {isOpen ? "Hide chunk metadata" : "View complete chunk metadata"}
      </button>

      {isOpen ? (
        <dl className="citation-metadata-grid">
          <div>
            <dt>Citation index</dt>
            <dd>{citation.citation_index}</dd>
          </div>

          <div>
            <dt>Retrieval score</dt>
            <dd>{citation.score.toFixed(6)}</dd>
          </div>

          <div>
            <dt>Chunk ID</dt>
            <dd>{displayValue(citation.chunk_id)}</dd>
          </div>

          <div>
            <dt>Document ID</dt>
            <dd>{displayValue(citation.doc_id)}</dd>
          </div>

          <div>
            <dt>Document title</dt>
            <dd>{displayValue(citation.doc_title)}</dd>
          </div>

          <div>
            <dt>Document type</dt>
            <dd>{displayValue(citation.doc_type)}</dd>
          </div>

          <div>
            <dt>Source file</dt>
            <dd>{displayValue(citation.source_file)}</dd>
          </div>

          <div>
            <dt>Source URL</dt>
            <dd>
              {citation.source_url ? (
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open original source ↗
                </a>
              ) : (
                "Not available"
              )}
            </dd>
          </div>

          <div>
            <dt>Section path</dt>
            <dd>{displayValue(citation.section_path)}</dd>
          </div>

          <div>
            <dt>Item number</dt>
            <dd>{displayValue(citation.item_number)}</dd>
          </div>

          <div>
            <dt>PDF page</dt>
            <dd>{displayValue(citation.page_pdf)}</dd>
          </div>

          <div>
            <dt>Printed page</dt>
            <dd>{displayValue(citation.page_printed)}</dd>
          </div>

          <div>
            <dt>Content type</dt>
            <dd>{displayValue(citation.content_type)}</dd>
          </div>

          <div>
            <dt>Table caption</dt>
            <dd>{displayValue(citation.table_caption)}</dd>
          </div>

          <div>
            <dt>Pipeline status</dt>
            <dd>{response.guardrail_status}</dd>
          </div>

          <div>
            <dt>Guardrail reason</dt>
            <dd>{displayValue(response.guardrail_reason)}</dd>
          </div>

          <div>
            <dt>Request ID</dt>
            <dd>{displayValue(response.request_id)}</dd>
          </div>

          <div>
            <dt>Total latency</dt>
            <dd>{latencySeconds} seconds</dd>
          </div>
        </dl>
      ) : null}
    </article>
  );
}

export function CitationList({
  citations,
  response,
}: CitationListProps) {
  if (!citations.length) {
    return null;
  }

  return (
    <section className="citations-section">
      <div className="citation-section-heading">
        <div>
          <p className="eyebrow">Evidence and retrieval details</p>
          <h3>Sources supporting this answer</h3>
        </div>

        <span>{citations.length} cited chunks</span>
      </div>

      <p className="citation-intro">
        Each citation is bound to a retrieved chunk. Expand any source to
        inspect its document, page, section, chunk identifier, retrieval score,
        guardrail state, and request-level latency.
      </p>

      <div className="citation-grid-rich">
        {citations.map((citation) => (
          <CitationCard
            citation={citation}
            response={response}
            key={`${citation.chunk_id}-${citation.citation_index}`}
          />
        ))}
      </div>
    </section>
  );
}
