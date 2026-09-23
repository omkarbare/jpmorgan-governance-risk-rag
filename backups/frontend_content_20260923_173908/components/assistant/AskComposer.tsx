"use client";

import { useState, type FormEvent } from "react";

type AskComposerProps = {
  isLoading: boolean;
  onSubmit: (query: string) => void;
};

export function AskComposer({
  isLoading,
  onSubmit,
}: AskComposerProps) {
  const [query, setQuery] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = query.trim();

    if (!trimmed || isLoading) {
      return;
    }

    onSubmit(trimmed);
  }

  return (
    <form className="ask-composer" onSubmit={handleSubmit}>
      <label className="sr-only" htmlFor="rag-question">
        Ask a governance or risk question
      </label>

      <textarea
        id="rag-question"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Ask about the available governance, risk, or conduct documents..."
        rows={3}
        maxLength={4000}
        disabled={isLoading}
      />

      <div className="composer-footer">
        <span>
          Answers are generated from indexed project documents and include
          supporting citations.
        </span>

        <button type="submit" disabled={isLoading || !query.trim()}>
          {isLoading ? "Analyzing…" : "Ask assistant"}
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </form>
  );
}
