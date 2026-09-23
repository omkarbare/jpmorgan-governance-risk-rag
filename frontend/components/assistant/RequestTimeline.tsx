"use client";

import type { PipelineStep } from "@/lib/api";

const DEFAULT_STEPS: PipelineStep[] = [
  {
    id: "input_guardrail",
    label: "Input guardrails",
    status: "pending",
  },
  {
    id: "hybrid_retrieval",
    label: "Hybrid retrieval",
    status: "pending",
  },
  {
    id: "grounded_generation",
    label: "Grounded answer generation",
    status: "pending",
  },
  {
    id: "output_validation",
    label: "Citation and output checks",
    status: "pending",
  },
];

type RequestTimelineProps = {
  isRunning: boolean;
  steps?: PipelineStep[];
  blocked?: boolean;
};

function getDisplaySteps(
  isRunning: boolean,
  steps?: PipelineStep[],
  blocked?: boolean,
): PipelineStep[] {
  if (steps?.length) {
    return steps;
  }

  if (!isRunning) {
    return DEFAULT_STEPS;
  }

  return DEFAULT_STEPS.map((step, index) => ({
    ...step,
    status:
      index === 0
        ? "completed"
        : index === 1
          ? "running"
          : blocked
            ? "blocked"
            : "pending",
  }));
}

export function RequestTimeline({
  isRunning,
  steps,
  blocked,
}: RequestTimelineProps) {
  const displaySteps = getDisplaySteps(isRunning, steps, blocked);

  return (
    <section
      className="timeline"
      aria-live="polite"
      aria-label="Request processing status"
    >
      <div className="timeline-heading">
        <span>How this answer was produced</span>
        {isRunning ? <em>Processing request</em> : null}
      </div>

      <ol>
        {displaySteps.map((step) => (
          <li className={`timeline-step ${step.status}`} key={step.id}>
            <span className="step-marker" aria-hidden="true">
              {step.status === "completed"
                ? "✓"
                : step.status === "blocked"
                  ? "×"
                  : ""}
            </span>

            <span className="step-label">{step.label}</span>

            <span className="step-state">
              {step.status === "running"
                ? "Running"
                : step.status === "completed"
                  ? "Complete"
                  : step.status === "blocked"
                    ? "Not run"
                    : "Queued"}

              {typeof step.duration_ms === "number"
                ? ` · ${step.duration_ms} ms`
                : ""}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
