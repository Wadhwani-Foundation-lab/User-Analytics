"use client";

import { Provenance } from "@/lib/types";

interface ProvenanceBadgeProps {
  provenance: Provenance;
}

function formatMetricName(name: string): string {
  return name
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function ProvenanceBadge({ provenance }: ProvenanceBadgeProps) {
  if (!provenance.certified) return null;

  const confidence =
    provenance.confidence != null
      ? `${Math.round(provenance.confidence * 100)}%`
      : null;

  const metricLabel = provenance.metric
    ? formatMetricName(provenance.metric)
    : null;

  return (
    <div className="provenance-badge" title={provenance.metric_source ?? undefined}>
      <span className="provenance-icon">✓</span>
      <span className="provenance-label">Certified metric</span>
      {metricLabel && (
        <>
          <span className="provenance-sep">·</span>
          <span className="provenance-metric">{metricLabel}</span>
        </>
      )}
      {confidence && (
        <>
          <span className="provenance-sep">·</span>
          <span className="provenance-confidence">{confidence} confidence</span>
        </>
      )}
    </div>
  );
}
