const documents = [
  {
    title: "Code of Conduct",
    file: "code-of-conduct.pdf",
    type: "Conduct and ethics",
    description:
      "Describes expected standards of behavior, integrity, conflicts of interest, gifts and hospitality, confidentiality, reporting concerns, and responsibilities for employees and directors.",
    topics: [
      "Ethical conduct",
      "Conflicts of interest",
      "Gifts and hospitality",
      "Confidential information",
      "Reporting concerns",
    ],
    link: "/documents/code-of-conduct.pdf",
  },
  {
    title: "Governance Principles",
    file: "governance-principles.pdf",
    type: "Board governance",
    description:
      "Defines the governance framework for the Board, including director responsibilities, independence, committee oversight, succession planning, and governance accountability.",
    topics: [
      "Board responsibilities",
      "Director independence",
      "Board committees",
      "Succession planning",
      "Governance accountability",
    ],
    link: "/documents/governance-principles.pdf",
  },
  {
    title: "Annual Report / 10-K",
    file: "jpmorgan-10-k.pdf",
    type: "Risk and disclosures",
    description:
      "Provides public-company disclosures about business activities, material risk factors, operational and financial risks, capital, liquidity, regulation, and risk management.",
    topics: [
      "Risk factors",
      "Operational risk",
      "Market and credit risk",
      "Liquidity and capital",
      "Regulatory environment",
    ],
    link: "/documents/jpmorgan-10-k.pdf",
  },
];

export default function DocumentsPage() {
  return (
    <main className="information-page">
      <header className="information-hero">
        <a className="back-link" href="/">
          ← Return to assistant
        </a>

        <p className="eyebrow light">Source library</p>
        <h1>Indexed documents</h1>
        <p>
          Three source documents support the assistant&apos;s grounded answers.
          Each result includes document, section, page, and retrieval metadata.
        </p>
      </header>

      <section className="information-content">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Document coverage</p>
            <h2>What the assistant can use</h2>
          </div>

          <p>
            Questions outside this collection should receive an insufficient
            evidence response rather than an unsupported answer.
          </p>
        </div>

        <div className="document-grid">
          {documents.map((document) => (
            <article className="document-card" key={document.file}>
              <div className="document-card-header">
                <span className="document-type">{document.type}</span>
                <span className="document-mark">PDF</span>
              </div>

              <h2>{document.title}</h2>
              <p className="document-file">{document.file}</p>
              <p>{document.description}</p>

              <div className="topic-list">
                {document.topics.map((topic) => (
                  <span key={topic}>{topic}</span>
                ))}
              </div>

              <a className="document-link" href={document.link}>
                Open source document →
              </a>
            </article>
          ))}
        </div>

        <section className="document-note">
          <p className="eyebrow">Metadata used in retrieval</p>
          <h2>Every chunk carries context</h2>
          <p>
            Indexed chunks retain document ID, document title, source file,
            document type, section path, item number, PDF page, printed page,
            content type, and optional table caption. This metadata is used for
            citation display, filtering, evaluation, and auditability.
          </p>
        </section>
      </section>
    </main>
  );
}
