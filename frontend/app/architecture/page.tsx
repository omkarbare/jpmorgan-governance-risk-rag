const layers = [
  {
    number: "01",
    title: "Document ingestion and parsing",
    description:
      "PDFs are parsed into clean, structured chunks while preserving page numbers, section paths, item references, content type, source file, and table metadata.",
    technologies: "PDF extraction · structure-aware chunking · JSONL",
  },
  {
    number: "02",
    title: "Dense semantic retrieval",
    description:
      "Chunks are embedded into vector representations so paraphrased governance and risk questions can retrieve conceptually related evidence.",
    technologies: "Sentence Transformers · Qdrant dense vectors",
  },
  {
    number: "03",
    title: "Sparse exact-term retrieval",
    description:
      "A sparse lexical index supports exact terms such as section numbers, committee names, defined terms, and document-specific wording.",
    technologies: "Token vocabulary · sparse vectors · BM25-like scoring",
  },
  {
    number: "04",
    title: "Hybrid reciprocal-rank fusion",
    description:
      "Dense and sparse rankings are combined using reciprocal-rank fusion. This is designed to balance paraphrase recall with exact-term precision.",
    technologies: "Dense retrieval · sparse retrieval · RRF",
  },
  {
    number: "05",
    title: "Grounded generation",
    description:
      "The language model receives the user question and retrieved chunks with instructions to answer only from the supplied evidence and use numbered citations.",
    technologies: "Groq primary route · OpenAI fallback · retries and routing",
  },
  {
    number: "06",
    title: "Guardrails and citation validation",
    description:
      "Input checks identify prompt injection, sensitive data, unsafe control-evasion requests, and out-of-scope questions. Output checks validate citation indices and insufficient-evidence behavior.",
    technologies: "Input guardrails · output validation · citation binding",
  },
];

export default function ArchitecturePage() {
  return (
    <main className="information-page">
      <header className="information-hero">
        <a className="back-link" href="/">
          ← Return to assistant
        </a>

        <p className="eyebrow light">System design</p>
        <h1>Architecture decisions</h1>
        <p>
          A transparent view of how the assistant parses documents, retrieves
          evidence, generates answers, and applies safety controls.
        </p>
      </header>

      <section className="information-content">
        <div className="section-heading">
          <div>
            <p className="eyebrow">End-to-end pipeline</p>
            <h2>From source PDF to cited answer</h2>
          </div>

          <p>
            The design separates retrieval quality, generation quality, and
            guardrail effectiveness so each layer can be evaluated independently.
          </p>
        </div>

        <div className="architecture-flow">
          {layers.map((layer) => (
            <article className="architecture-card" key={layer.number}>
              <span className="architecture-number">{layer.number}</span>

              <div>
                <h2>{layer.title}</h2>
                <p>{layer.description}</p>
                <span className="architecture-tech">
                  {layer.technologies}
                </span>
              </div>
            </article>
          ))}
        </div>

        <section className="decision-grid">
          <article>
            <p className="eyebrow">Why hybrid retrieval?</p>
            <h2>Different questions need different signals.</h2>
            <p>
              Dense retrieval helps with paraphrases and semantic similarity.
              Sparse retrieval helps with exact section numbers, committee
              names, and defined terms. RRF provides a simple, inspectable way
              to combine both ranked lists.
            </p>
          </article>

          <article>
            <p className="eyebrow">Why citations?</p>
            <h2>Evidence should be inspectable.</h2>
            <p>
              Citations are bound to retrieved chunk indices and expose source
              document, page, section, and retrieval score. This makes the
              answer easier to review and helps prevent unsupported claims.
            </p>
          </article>

          <article>
            <p className="eyebrow">Why guardrails?</p>
            <h2>Scope is part of reliability.</h2>
            <p>
              A system that answers every question is not necessarily reliable.
              Input and output controls help it refuse unsafe, unsupported, or
              insufficiently evidenced requests.
            </p>
          </article>
        </section>
      </section>
    </main>
  );
}
