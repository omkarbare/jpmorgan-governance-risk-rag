"use client";

import {
  BarChart3,
  BookOpenText,
  BrainCircuit,
  Building2,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Copy,
  FileText,
  KeyRound,
  LayoutDashboard,
  Network,
  Send,
  ShieldCheck,
  UsersRound,
  X,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type { AskResponse, Citation } from "@/lib/types";

const suggestions = [
  "What is the Code of Conduct?",
  "How does JPMorgan manage operational risk?",
  "Summarize the Board Risk Committee charter.",
  "What are the main risk factors in the 10-K?",
  "Explain the firm's enterprise risk management framework.",
];

type View = "assistant" | "documents" | "architecture";

const documents = [
  {
    type: "10-K",
    title: "JPMorgan Chase & Co. Form 10-K",
    description:
      "The annual filing provides the broadest view of business risks, Item 1A risk factors, financial exposures, controls, and regulatory disclosures.",
    rationale:
      "Included as the primary risk source because it contains formal, externally filed risk disclosures and useful item/page citation anchors.",
    linkLabel: "Open official SEC filing",
    url: "https://www.sec.gov/edgar/browse/?CIK=19617",
    icon: FileText,
  },
  {
    type: "Governance",
    title: "Corporate Governance Principles",
    description:
      "Defines board responsibilities, oversight expectations, governance principles, and the relationship between directors and management.",
    rationale:
      "Included to answer questions about governance design, accountability, board oversight, and decision rights.",
    linkLabel: "Open JPMorgan governance page",
    url: "https://www.jpmorganchase.com/about/governance",
    icon: ShieldCheck,
  },
  {
    type: "Conduct",
    title: "Code of Conduct",
    description:
      "Provides practical expectations for ethical behavior, conflicts of interest, gifts and hospitality, reporting concerns, and compliance.",
    rationale:
      "Included because policy and conduct questions require precise clause-level language rather than general model knowledge.",
    linkLabel: "Open JPMorgan Code of Conduct resources",
    url: "https://www.jpmorganchase.com/about/governance",
    icon: ClipboardList,
  },
];

const architectureDecisions = [
  {
    number: "01",
    title: "Structure-aware document parsing",
    status: "Implemented",
    body:
      "PDFs are converted into clean, citation-ready chunks. Table-of-contents pages are used as structural ground truth but are excluded from retrieval. Tables remain independent chunks, repeated headers and footers are removed, and every chunk keeps document, section, page, content-type, and provenance metadata.",
    icon: FileText,
  },
  {
    number: "02",
    title: "Dense and sparse retrieval",
    status: "Implemented",
    body:
      "Dense embeddings capture semantic meaning while sparse token vectors preserve exact terms such as Item 1A, Section 4.2, policy names, and risk labels. Qdrant stores both representations in the same collection.",
    icon: BrainCircuit,
  },
  {
    number: "03",
    title: "Reciprocal Rank Fusion",
    status: "Implemented",
    body:
      "The system retrieves independent dense and sparse rankings, combines them with RRF, and sends the strongest unified context to generation. This is useful when a question contains both a concept and an exact legal or policy phrase.",
    icon: BarChart3,
  },
  {
    number: "04",
    title: "Citation-first generation",
    status: "Implemented",
    body:
      "The LLM receives numbered evidence blocks and is instructed to cite only those numbers. The API validates citation markers and maps them back to chunk IDs, source files, section paths, and PDF/printed pages.",
    icon: BookOpenText,
  },
  {
    number: "05",
    title: "Provider resilience",
    status: "Implemented",
    body:
      "LiteLLM routes to Groq-hosted Qwen first and OpenAI GPT as fallback, with retries, timeouts, and response caching. The exact active provider can be exposed in a later response metadata enhancement.",
    icon: Network,
  },
  {
    number: "06",
    title: "Observability and evaluation",
    status: "In progress",
    body:
      "LangSmith traces retrieval and generation. The next evaluation phase will add a question set, retrieval recall measurements, citation support checks, latency tracking, and regression reports. This section is intentionally designed to evolve as evaluation work continues.",
    icon: LayoutDashboard,
  },
];

function citationLocation(citation: Citation) {
  const parts: string[] = [];
  if (citation.section_path) parts.push(citation.section_path);
  if (citation.item_number && !citation.section_path.includes(citation.item_number)) {
    parts.push(citation.item_number);
  }
  const page = citation.page_printed ?? citation.page_pdf;
  if (page !== null && page !== undefined) parts.push(`Page ${page}`);
  if (citation.content_type) parts.push(citation.content_type);
  return parts.join(" • ") || "Location metadata unavailable";
}

function renderAnswer(answer: string, onCitation: (index: number) => void) {
  const parts = answer.split(/(\[\d+\])/g);
  return parts.map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return <span key={index}>{part}</span>;
    const citationIndex = Number(match[1]);
    return (
      <button
        key={index}
        type="button"
        className="citation-inline"
        onClick={() => onCitation(citationIndex)}
        aria-label={`Open citation ${citationIndex}`}
      >
        [{citationIndex}]
      </button>
    );
  });
}

export default function GovernanceAssistant() {
  const [view, setView] = useState<View>("assistant");
  const [sessionKey, setSessionKey] = useState("");
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  const citationMap = useMemo(() => {
    return new Map((response?.citations ?? []).map((item) => [item.citation_index, item]));
  }, [response]);

  async function ask(question: string) {
    const normalized = question.trim();
    if (!normalized || loading) return;

    setQuery(normalized);
    setLoading(true);
    setError("");
    setActiveCitation(null);

    try {
      const result = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(sessionKey.trim() ? { "x-groq-api-key": sessionKey.trim() } : {}),
        },
        body: JSON.stringify({ query: normalized, top_k: 5 }),
      });

      const data = await result.json();
      if (!result.ok) {
        throw new Error(data.detail || "The backend could not answer this question.");
      }

      setResponse(data as AskResponse);
    } catch (caught) {
      setResponse(null);
      setError(caught instanceof Error ? caught.message : "Unexpected request error.");
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(query);
  }

  function copyAnswer() {
    if (!response?.answer) return;
    void navigator.clipboard.writeText(response.answer).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    });
  }

  function jumpToCitation(index: number) {
    if (!citationMap.has(index)) return;
    setActiveCitation(index);
    document.getElementById(`citation-${index}`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="brand">
            <div className="brand-name">JPMorgan</div>
            <div className="brand-kicker">CORPORATE GOVERNANCE &amp; RISK</div>
            <div className="brand-kicker">AI ASSISTANT</div>
          </div>

          <div className="sidebar-rule" />

          <div className="session-key-block">
            <div className="session-title-row">
              <label htmlFor="session-key">Groq API Key (Session Only)</label>
              <CircleHelp size={17} aria-label="The key is used for this browser session only" />
            </div>
            <div className="session-input-wrap">
              <KeyRound size={18} />
              <input
                id="session-key"
                type="password"
                value={sessionKey}
                onChange={(event) => setSessionKey(event.target.value)}
                placeholder="Enter your Groq API key"
                autoComplete="off"
              />
            </div>
            <p>Used only for this session.<br />Never stored.</p>
          </div>

          <nav className="side-nav" aria-label="Application navigation">
            <button className={view === "assistant" ? "nav-button active" : "nav-button"} onClick={() => setView("assistant")}>
              <LayoutDashboard size={25} />
              Assistant
            </button>
            <button className={view === "documents" ? "nav-button active" : "nav-button"} onClick={() => setView("documents")}>
              <FileText size={25} />
              Documents
            </button>
            <button className={view === "architecture" ? "nav-button active" : "nav-button"} onClick={() => setView("architecture")}>
              <Network size={25} />
              <span>Architecture<br />Decisions</span>
            </button>
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="footer-line" />
          <p>Created by Omkar Bare.</p>
          <span>This project is for educational purposes only and is not affiliated with JPMorgan Chase.</span>
        </div>
      </aside>

      <main className="main-content">
        {view === "assistant" && (
          <>
            <section className="hero">
              <div className="hero-content">
                <h1>JPMorgan Corporate<br />Governance &amp; Risk Assistant</h1>
              </div>
            </section>

            <section className="assistant-page">
              <div className="capability-grid">
                <Capability icon={FileText} title="Policy & Governance" text="Access and understand key policies and frameworks" />
                <Capability icon={ShieldCheck} title="Risk Insights" text="Get answers on risk management, controls and compliance" />
                <Capability icon={BarChart3} title="Hybrid RAG" text="Combines internal documents with advanced retrieval strategy" />
                <Capability icon={UsersRound} title="Informed Decisions" text="Support better, faster and safer decisions" />
              </div>

              <form className="ask-form" onSubmit={submit}>
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Ask a question about JPMorgan's corporate governance, risk policies, frameworks, or related topics..."
                  rows={3}
                  aria-label="Ask a question"
                />
                <button type="submit" disabled={loading || !query.trim()} aria-label="Send question">
                  <Send size={21} />
                </button>
              </form>

              {loading && <div className="loading-line"><span className="spinner" /> Retrieving sources and generating a cited answer…</div>}
              {error && <div className="error-panel"><strong>Request failed:</strong> {error}</div>}

              <div className="try-row">
                <strong>Try asking:</strong>
                <div className="suggestions">
                  {suggestions.map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => void ask(suggestion)}>{suggestion}</button>
                  ))}
                </div>
              </div>

              {response && (
                <section className="answer-panel" aria-live="polite">
                  <div className="answer-heading">
                    <div>
                      <span className="section-label">GROUNDED RESPONSE</span>
                      <h2>Answer</h2>
                    </div>
                    <button className="copy-button" type="button" onClick={copyAnswer}>
                      {copied ? <Check size={15} /> : <Copy size={15} />}
                      {copied ? "Copied" : "Copy answer"}
                    </button>
                  </div>

                  <div className="answer-body">
                    {renderAnswer(response.answer, jumpToCitation)}
                  </div>

                  <div className="stats-grid">
                    <Stat label="Latency" value={`${response.latency_ms} ms`} />
                    <Stat label="Retrieved" value={String(response.retrieval_count)} />
                    <Stat label="Cited" value={String(response.citation_count)} />
                    <Stat label="Request ID" value={response.request_id} wide />
                  </div>

                  <div className="sources-heading">
                    <div>
                      <span className="section-label">VERIFIABLE SOURCES</span>
                      <h2>Citations</h2>
                    </div>
                    <span className="source-count">{response.citations.length} sources</span>
                  </div>

                  <div className="citation-list">
                    {response.citations.map((citation) => (
                      <article
                        key={citation.citation_index}
                        id={`citation-${citation.citation_index}`}
                        className={activeCitation === citation.citation_index ? "citation-card highlighted" : "citation-card"}
                      >
                        <div className="citation-top">
                          <span className="citation-number">[{citation.citation_index}]</span>
                          <div className="citation-title-block">
                            <strong>{citation.doc_title || citation.source_file}</strong>
                            <span>{citation.doc_type || "Document"}</span>
                          </div>
                          <small>RRF {citation.score.toFixed(4)}</small>
                        </div>
                        <p>{citationLocation(citation)}</p>
                        <small>{citation.source_file} · {citation.chunk_id}</small>
                      </article>
                    ))}
                  </div>
                </section>
              )}
            </section>
          </>
        )}

        {view === "documents" && <DocumentsView />}
        {view === "architecture" && <ArchitectureView />}
      </main>
    </div>
  );
}

function Capability({ icon: Icon, title, text }: { icon: typeof FileText; title: string; text: string }) {
  return (
    <article className="capability">
      <Icon size={43} strokeWidth={1.65} />
      <h2>{title}</h2>
      <p>{text}</p>
    </article>
  );
}

function Stat({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "stat wide" : "stat"}>
      <span>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function DocumentsView() {
  return (
    <section className="subpage">
      <header className="subpage-header">
        <span className="section-label">INDEXED KNOWLEDGE BASE</span>
        <h1>Documents</h1>
        <p>
          These three sources were selected to give the assistant complementary coverage: formal risk disclosures, governance design, and practical conduct requirements.
        </p>
      </header>

      <div className="document-grid">
        {documents.map(({ icon: Icon, ...document }) => (
          <article className="document-card" key={document.title}>
            <div className="document-icon"><Icon size={30} /></div>
            <span className="document-type">{document.type}</span>
            <h2>{document.title}</h2>
            <p>{document.description}</p>
            <div className="rationale"><strong>Why it is included</strong><span>{document.rationale}</span></div>
            <a href={document.url} target="_blank" rel="noreferrer">
              {document.linkLabel}<ChevronRight size={15} />
            </a>
          </article>
        ))}
      </div>

      <div className="document-note">
        <strong>Provenance note</strong>
        <p>
          The links above are the official or authoritative source locations. The local PDFs under <code>data/raw_pdfs/</code> are the versions actually parsed and indexed. When the local file changes, re-run parsing and indexing so citations continue to match the indexed version.
        </p>
      </div>
    </section>
  );
}

function ArchitectureView() {
  return (
    <section className="subpage">
      <header className="subpage-header">
        <span className="section-label">EMPLOYER-READY SYSTEM DESIGN</span>
        <h1>Architecture Decisions</h1>
        <p>
          This page explains why each major RAG architecture decision exists, what problem it solves, and how the design will evolve as evaluations reveal new quality or operational requirements.
        </p>
      </header>

      <div className="architecture-intro">
        <div><Building2 size={30} /></div>
        <div>
          <strong>Current end-to-end flow</strong>
          <p>Source PDFs → structure-aware parsing → metadata-rich chunks → dense and sparse Qdrant vectors → RRF → LiteLLM generation → validated citations → LangSmith traces.</p>
        </div>
      </div>

      <div className="architecture-grid">
        {architectureDecisions.map(({ icon: Icon, ...decision }) => (
          <article className="architecture-card" key={decision.number}>
            <div className="architecture-card-top">
              <span className="decision-number">{decision.number}</span>
              <Icon size={27} />
            </div>
            <span className={decision.status === "In progress" ? "status progress" : "status"}>{decision.status}</span>
            <h2>{decision.title}</h2>
            <p>{decision.body}</p>
          </article>
        ))}
      </div>

      <div className="roadmap-panel">
        <span className="section-label">NEXT EVALUATION LOOP</span>
        <h2>How this page will evolve</h2>
        <p>
          As evaluation questions are added, this section will be updated with retrieval recall, citation support rate, answer faithfulness, latency percentiles, provider fallback frequency, and documented trade-offs. The architecture is intentionally treated as a living decision record rather than a static diagram.
        </p>
      </div>
    </section>
  );
}
