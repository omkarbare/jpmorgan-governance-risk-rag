import { MetricCard } from "@/components/evaluation/MetricCard";

type RetrievalMethod = {
  method: string;
  top_k: number;
  questions_evaluated: number;
  hits: number;
  hit_rate: number;
  mrr: number;
};

type RetrievalSummary = {
  generated_at?: string;
  methods?: RetrievalMethod[];
};

type RagSummary = {
  generated_at?: string;
  total_cases?: number;
  passed_cases?: number;
  failed_cases?: number;
  pass_rate?: number;
  guardrail_block_rate?: number | null;
  citation_presence_rate?: number | null;
  expected_document_hit_rate?: number | null;
  latency_ms?: {
    count?: number;
    mean?: number | null;
    median?: number | null;
    p95?: number | null;
  };
};

function formatPercent(value?: number | null): string {
  if (typeof value !== "number") {
    return "Not measured";
  }

  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value?: number | null, suffix = ""): string {
  if (typeof value !== "number") {
    return "Not measured";
  }

  return `${Math.round(value).toLocaleString()}${suffix}`;
}

async function loadEvaluationJson<T>(fileName: string): Promise<T | null> {
  try {
    const response = await fetch(
      `http://localhost:3000/evaluation-data/${fileName}`,
      { cache: "no-store" },
    );

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default async function EvaluationPage() {
  const [retrievalSummary, ragSummary] = await Promise.all([
    loadEvaluationJson<RetrievalSummary>("retrieval_summary.json"),
    loadEvaluationJson<RagSummary>("latest_summary.json"),
  ]);

  const runDate =
    ragSummary?.generated_at ?? retrievalSummary?.generated_at ?? null;

  const methods = retrievalSummary?.methods ?? [];

  return (
    <main className="evaluation-page">
      <header className="evaluation-hero">
        <a className="back-link" href="/">
          ← Return to assistant
        </a>

        <p className="eyebrow light">Quality assurance and reliability</p>

        <h1>Evaluation &amp; Reliability</h1>

        <p>
          Measured performance across retrieval, citations, refusal behavior,
          guardrails, and operational latency.
        </p>

        <small>
          {runDate
            ? `Latest recorded run: ${new Date(runDate).toLocaleString()}`
            : "No local evaluation result files have been loaded yet."}
        </small>
      </header>

      <section className="evaluation-content">
        <section>
          <div className="section-heading">
            <div>
              <p className="eyebrow">At a glance</p>
              <h2>System-quality indicators</h2>
            </div>

            <p>
              Values are read from local evaluation artifacts. Unavailable
              metrics are not estimated or fabricated.
            </p>
          </div>

          <div className="metric-grid">
            <MetricCard
              label="End-to-end pass rate"
              value={formatPercent(ragSummary?.pass_rate)}
              detail={
                ragSummary?.total_cases
                  ? `${ragSummary.passed_cases ?? 0} of ${ragSummary.total_cases} cases passed`
                  : "Run the RAG evaluator to populate"
              }
            />

            <MetricCard
              label="Citation presence"
              value={formatPercent(ragSummary?.citation_presence_rate)}
              detail="Answered cases requiring supporting citations"
            />

            <MetricCard
              label="Guardrail block accuracy"
              value={formatPercent(ragSummary?.guardrail_block_rate)}
              detail="Expected blocked requests stopped safely"
            />

            <MetricCard
              label="P95 API latency"
              value={formatNumber(ragSummary?.latency_ms?.p95, " ms")}
              detail={`Mean ${formatNumber(ragSummary?.latency_ms?.mean, " ms")} across recorded responses`}
            />
          </div>
        </section>

        <section className="evaluation-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Retrieval quality</p>
              <h2>Does hybrid retrieval outperform a single method?</h2>
            </div>

            <p>
              Hit rate measures whether the annotated relevant source appears
              in the top-k results. MRR rewards a higher rank.
            </p>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Retrieval method</th>
                  <th>Test questions</th>
                  <th>Hits</th>
                  <th>Hit rate@k</th>
                  <th>MRR</th>
                </tr>
              </thead>

              <tbody>
                {methods.length > 0 ? (
                  methods.map((method) => (
                    <tr key={method.method}>
                      <td>
                        {method.method === "hybrid"
                          ? "Hybrid (RRF)"
                          : `${method.method} only`}
                      </td>
                      <td>{method.questions_evaluated}</td>
                      <td>{method.hits}</td>
                      <td>{formatPercent(method.hit_rate)}</td>
                      <td>{method.mrr.toFixed(3)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="empty-row" colSpan={5}>
                      No retrieval summary found. Run{" "}
                      <code>python scripts/evaluate_retrieval.py</code>, then
                      copy the output into{" "}
                      <code>frontend/public/evaluation-data/</code>.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="evaluation-section qa-grid">
          <article>
            <p className="eyebrow">Question</p>
            <h2>How does the system handle unsupported questions?</h2>
            <p>
              It is designed to identify insufficient evidence and avoid
              fabricating an answer. Refusal and abstention behavior are
              measured in the RAG evaluation suite.
            </p>
            <p className="qa-stat">
              Expected-document hit rate:{" "}
              <strong>
                {formatPercent(ragSummary?.expected_document_hit_rate)}
              </strong>
            </p>
          </article>

          <article>
            <p className="eyebrow">Question</p>
            <h2>How are prompt injection and sensitive inputs handled?</h2>
            <p>
              Input guardrails inspect requests before document retrieval or
              model generation. Blocked requests return no retrieved chunks and
              no model output.
            </p>
            <p className="qa-stat">
              Guardrail block accuracy:{" "}
              <strong>
                {formatPercent(ragSummary?.guardrail_block_rate)}
              </strong>
            </p>
          </article>

          <article>
            <p className="eyebrow">Question</p>
            <h2>How can reviewers inspect the evidence?</h2>
            <p>
              Each grounded answer displays citations with document, page,
              section metadata, retrieval score, pipeline status, and latency.
            </p>
            <p className="qa-stat">
              Citation presence:{" "}
              <strong>
                {formatPercent(ragSummary?.citation_presence_rate)}
              </strong>
            </p>
          </article>
        </section>

        <section className="evaluation-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Methodology</p>
              <h2>How the results are produced</h2>
            </div>
          </div>

          <div className="methodology-grid">
            <p>
              <strong>Dataset:</strong> a versioned question set spanning
              factual, paraphrased, exact-term, cross-document, unanswerable,
              and adversarial cases.
            </p>

            <p>
              <strong>Retrieval:</strong> annotated source expectations are
              evaluated with Hit@k and mean reciprocal rank.
            </p>

            <p>
              <strong>Generation:</strong> evaluation covers citation presence,
              grounding controls, refusal behavior, guardrail outcomes, and
              response latency.
            </p>

            <p>
              <strong>Reproducibility:</strong> raw JSON and CSV output is
              generated by project evaluation scripts and retained with dated
              runs.
            </p>
          </div>
        </section>

        <section className="evaluation-section limitations">
          <p className="eyebrow">Current limitations</p>
          <h2>What the system is still improving</h2>

          <ul>
            <li>
              Cross-document and multi-hop questions require more complete
              golden-chunk annotation and dedicated reranking tests.
            </li>
            <li>
              Document classification metadata should be normalized so
              source-type filters and evaluation labels stay consistent.
            </li>
            <li>
              Generation-quality scoring should combine human review with an
              independently configured LLM judge; neither is a guarantee.
            </li>
          </ul>
        </section>
      </section>
    </main>
  );
}
