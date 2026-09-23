"use client";

import { useState } from "react";
import { AnswerCard } from "@/components/assistant/AnswerCard";
import { AskComposer } from "@/components/assistant/AskComposer";
import { RequestTimeline } from "@/components/assistant/RequestTimeline";
import { GuardrailExamples } from "@/components/site/GuardrailExamples";
import { askRag, type ApiRequestError, type AskResponse } from "@/lib/api";

const suggestedQueries = [
  "What are the main responsibilities of the Board in corporate governance?",
  "How does JPMorgan manage operational risk?",
  "What does the Code of Conduct say about gifts and business hospitality?",
  "What are the main risk factors described in Item 1A?",
];

export default function HomePage() {
  const [groqApiKey, setGroqApiKey] = useState("");
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState("");
  const [requiresApiKey, setRequiresApiKey] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  async function submitQuestion(query: string) {
    setQuestion(query);
    setResponse(null);
    setError("");
    setRequiresApiKey(false);
    setIsLoading(true);

    try {
      const result = await askRag(
        query,
        groqApiKey.trim() || undefined,
        openaiApiKey.trim() || undefined,
      );

      setResponse(result);
    } catch (requestError) {
      const apiError = requestError as ApiRequestError;

      setRequiresApiKey(Boolean(apiError.providerLimit));

      setError(
        requestError instanceof Error
          ? requestError.message
          : "The request could not be completed. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="site-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-wordmark">JPMorgan</span>
          <span>Corporate Governance &amp; Risk</span>
          <span>AI Assistant</span>
        </div>

        <div className="sidebar-rule" />

        <label className="key-label" htmlFor="groq-key">
          Groq API key <span>(session only)</span>
        </label>

        <input
          id="groq-key"
          type="password"
          autoComplete="off"
          value={groqApiKey}
          onChange={(event) => setGroqApiKey(event.target.value)}
          placeholder="Enter your Groq API key"
        />

        <p className="sidebar-note">
          Enter your own Groq key to use it for this request. The key remains
          in browser memory only and is sent only to your local API endpoint.
        </p>

        <a
          className="api-key-link"
          href="https://console.groq.com/keys"
          target="_blank"
          rel="noreferrer"
        >
          Create a Groq API key ↗
        </a>

        <label className="key-label" htmlFor="openai-key">
          OpenAI API key <span>(optional fallback)</span>
        </label>

        <input
          id="openai-key"
          type="password"
          autoComplete="off"
          value={openaiApiKey}
          onChange={(event) => setOpenaiApiKey(event.target.value)}
          placeholder="Enter your OpenAI API key"
        />

        <p className="sidebar-note">
          Optional fallback for provider limits and load balancing.
        </p>

        <a
          className="api-key-link"
          href="https://platform.openai.com/api-keys"
          target="_blank"
          rel="noreferrer"
        >
          Create an OpenAI API key ↗
        </a>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          <a className="active" href="/">Assistant</a>
          <a href="/documents">Documents</a>
          <a href="/architecture">Architecture decisions</a>
          <a href="/evaluation">Evaluation &amp; reliability</a>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-rule" />
          <p>Created by Omkar Bare.</p>
          <small>
            This educational project is not affiliated with JPMorgan Chase.
          </small>
        </div>
      </aside>

      <section className="content-area">
        <header className="hero">
          <div className="hero-overlay">
            <p className="eyebrow light">Corporate governance intelligence</p>

            <h1>
              JPMorgan Corporate
              <br />
              Governance &amp; Risk Assistant
            </h1>

            <p>
              Grounded answers from indexed governance, conduct, and risk
              documents.
            </p>
          </div>
        </header>

        <section className="value-strip">
          <article>
            <span className="value-icon">▤</span>
            <h3>Policy &amp; governance</h3>
            <p>Navigate governance principles and policy material.</p>
          </article>

          <article>
            <span className="value-icon">◈</span>
            <h3>Risk insights</h3>
            <p>Find evidence in risk disclosures and frameworks.</p>
          </article>

          <article>
            <span className="value-icon">⌘</span>
            <h3>Hybrid RAG</h3>
            <p>Combines semantic and exact-term retrieval.</p>
          </article>

          <article>
            <span className="value-icon">◎</span>
            <h3>Guarded responses</h3>
            <p>Safety checks, evidence limits, and citations.</p>
          </article>
        </section>

        <section className="assistant-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Document-grounded assistant</p>
              <h2>Ask a governance or risk question</h2>
            </div>

            <a href="/evaluation">View evaluation results →</a>
          </div>

          <AskComposer
            isLoading={isLoading}
            onSubmit={submitQuestion}
          />

          {!response && !isLoading && !error ? (
            <div className="suggestions">
              <span>Try asking</span>

              {suggestedQueries.map((query) => (
                <button
                  key={query}
                  type="button"
                  onClick={() => submitQuestion(query)}
                >
                  {query}
                </button>
              ))}
            </div>
          ) : null}

          {isLoading ? <RequestTimeline isRunning /> : null}

          {error ? (
            <section className="error-card" role="alert">
              <p className="eyebrow">
                {requiresApiKey ? "Provider limit or authentication issue" : "Service unavailable"}
              </p>

              <h3>
                {requiresApiKey
                  ? "Enter your own API key to continue."
                  : "We could not complete this request."}
              </h3>

              <p>{error}</p>

              {requiresApiKey ? (
                <div className="provider-key-actions">
                  <p>
                    A model-provider limit, quota, or authentication issue may
                    have occurred. Add a valid Groq key above, or add an OpenAI
                    key if fallback routing is enabled in the backend.
                  </p>

                  <div>
                    <a
                      href="https://console.groq.com/keys"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Create Groq key ↗
                    </a>

                    <a
                      href="https://platform.openai.com/api-keys"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Create OpenAI key ↗
                    </a>
                  </div>
                </div>
              ) : (
                <p className="error-note">
                  Confirm that the backend is running and that your API key is valid.
                </p>
              )}
            </section>
          ) : null}

          {response ? (
            <AnswerCard question={question} response={response} />
          ) : null}
        </section>

        <GuardrailExamples />
      </section>
    </main>
  );
}
