import type { AskResponse } from "@/lib/api";
import { CitationList } from "./CitationList";
import { RunMetadata } from "./RunMetadata";

type AnswerCardProps = {
  response: AskResponse;
  question: string;
};

function getParagraphs(answer: string) {
  return answer
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

export function AnswerCard({
  response,
  question,
}: AnswerCardProps) {
  const isBlocked = response.guardrail_status === "blocked";

  const isInsufficientEvidence =
    response.guardrail_reason === "insufficient_evidence";

  return (
    <article className={`answer-card ${isBlocked ? "blocked-card" : ""}`}>
      <header className="answer-header">
        <p className="eyebrow">Your question</p>
        <h2>{question}</h2>
      </header>

      <RunMetadata response={response} />

      <section className="answer-body">
        <p className="eyebrow">
          {isBlocked
            ? "Request blocked"
            : isInsufficientEvidence
              ? "Evidence check"
              : "Grounded response"}
        </p>

        {getParagraphs(response.answer).map((paragraph, index) => (
          <p key={`${index}-${paragraph.slice(0, 25)}`}>
            {paragraph}
          </p>
        ))}
      </section>

      {!isBlocked ? (
        <CitationList citations={response.citations} response={response} />
      ) : null}
    </article>
  );
}
