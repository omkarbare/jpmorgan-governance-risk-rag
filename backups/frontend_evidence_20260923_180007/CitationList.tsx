import type { Citation } from "@/lib/api";

type CitationListProps = {
  citations: Citation[];
};

export function CitationList({ citations }: CitationListProps) {
  if (!citations.length) {
    return null;
  }

  return (
    <section className="citations-section">
      <p className="eyebrow">Supporting evidence</p>

      <div className="citation-grid">
        {citations.map((citation) => {
          const page = citation.page_printed ?? citation.page_pdf;

          const location = [
            citation.section_path,
            citation.item_number,
            page ? `Page ${page}` : "",
          ]
            .filter(Boolean)
            .join(" · ");

          return (
            <article
              className="citation-card"
              key={`${citation.chunk_id}-${citation.citation_index}`}
            >
              <span className="citation-number">
                [{citation.citation_index}]
              </span>

              <div>
                <h4>
                  {citation.doc_title ||
                    citation.source_file ||
                    "Source document"}
                </h4>

                <p>{location || "Document excerpt"}</p>

                <span className="citation-meta">
                  Retrieval score {citation.score.toFixed(3)} ·{" "}
                  {citation.content_type}
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
