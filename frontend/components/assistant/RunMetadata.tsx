"use client";

import { useState } from "react";
import type { AskResponse } from "@/lib/api";

type RunMetadataProps = {
  response: AskResponse;
};

export function RunMetadata({ response }: RunMetadataProps) {
  const [isOpen, setIsOpen] = useState(false);

  const displayStatus =
    response.guardrail_status === "blocked"
      ? "Blocked"
      : response.guardrail_reason === "insufficient_evidence"
        ? "Insufficient evidence"
        : "Grounded answer";

  const latencySeconds = (response.latency_ms / 1000).toFixed(2);

  return (
    <section className="run-metadata">
      <div className="metadata-summary">
        <span className={`status-pill ${response.guardrail_status}`}>
          {displayStatus}
        </span>

        <span>{latencySeconds} seconds</span>
        <span>{response.retrieval_count} chunks retrieved</span>
        <span>{response.citation_count} citations</span>
        <span>Guardrails {response.guardrail_status}</span>
      </div>

      <button
        className="details-button"
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        aria-expanded={isOpen}
      >
        {isOpen ? "Hide technical details" : "Show technical details"}
      </button>

      {isOpen ? (
        <dl className="metadata-details">
          <div>
            <dt>Request ID</dt>
            <dd>{response.request_id}</dd>
          </div>

          <div>
            <dt>Latency</dt>
            <dd>{latencySeconds} seconds</dd>
          </div>

          <div>
            <dt>Model route</dt>
            <dd>{response.model}</dd>
          </div>

          <div>
            <dt>Collection</dt>
            <dd>{response.collection}</dd>
          </div>

          <div>
            <dt>Guardrail status</dt>
            <dd>{response.guardrail_status}</dd>
          </div>

          <div>
            <dt>Guardrail reason</dt>
            <dd>{response.guardrail_reason ?? "None"}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
