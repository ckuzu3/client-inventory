import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ComplianceSummary, Severity } from '../models/inventory';

/** One severity row in the breakdown. */
interface SeverityCount {
  readonly severity: Severity;
  readonly count: number;
}

const SEVERITY_ORDER: readonly Severity[] = ['high', 'medium', 'low'];

/**
 * The tiles a dashboard opens with.
 *
 * Presentational on purpose: it takes a summary and renders it, it fetches nothing and
 * it holds no state. That is what makes its test a single `setInput` and an assertion
 * on the rendered text.
 */
@Component({
  selector: 'app-summary-cards',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="cards" aria-label="Fleet summary">
      <article class="card">
        <h3>Clients</h3>
        <p class="figure">{{ summary().total_clients }}</p>
      </article>

      <article class="card ok">
        <h3>Compliant</h3>
        <p class="figure">{{ summary().compliant_clients }}</p>
        <p class="note">{{ compliantPercent() }}% of the fleet</p>
      </article>

      <article class="card attention">
        <h3>Needs attention</h3>
        <p class="figure">{{ summary().noncompliant_clients }}</p>
        <p class="note">{{ totalFindings() }} findings in total</p>
      </article>

      <article class="card">
        <h3>By severity</h3>
        <ul class="severities">
          @for (entry of severityCounts(); track entry.severity) {
            <li>
              <span class="badge {{ entry.severity }}">{{ entry.severity }}</span>
              <span>{{ entry.count }}</span>
            </li>
          } @empty {
            <li class="note">Nothing to report.</li>
          }
        </ul>
      </article>
    </section>
  `,
  styles: `
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
      gap: 0.75rem;
    }

    .card {
      background: #fff;
      border: 1px solid #e2e2e6;
      border-radius: 0.5rem;
      padding: 0.9rem 1rem;
    }

    .card.ok {
      border-left: 4px solid #2f7d32;
    }

    .card.attention {
      border-left: 4px solid #b3261e;
    }

    h3 {
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      margin: 0 0 0.4rem;
      text-transform: uppercase;
      color: #55555c;
    }

    .figure {
      font-size: 1.9rem;
      font-weight: 600;
      margin: 0;
      font-variant-numeric: tabular-nums;
    }

    .note {
      color: #55555c;
      font-size: 0.8rem;
      margin: 0.2rem 0 0;
    }

    .severities {
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .severities li {
      display: flex;
      gap: 0.5rem;
      align-items: center;
      font-variant-numeric: tabular-nums;
    }
  `,
})
export class SummaryCards {
  /** The counts to render. Required: there is no sensible empty state for a tile row. */
  readonly summary = input.required<ComplianceSummary>();

  /** Severity counts in a fixed worst-first order, skipping severities with no findings. */
  readonly severityCounts = computed<readonly SeverityCount[]>(() => {
    const counts = this.summary().findings_by_severity;

    return SEVERITY_ORDER.filter((severity) => (counts[severity] ?? 0) > 0).map((severity) => ({
      severity,
      count: counts[severity],
    }));
  });

  /** Total findings across the fleet. */
  readonly totalFindings = computed(() =>
    Object.values(this.summary().findings_by_severity).reduce((sum, count) => sum + count, 0),
  );

  /** Share of compliant clients, rounded. Zero clients reads as 0, not as a division error. */
  readonly compliantPercent = computed(() => {
    const summary = this.summary();
    if (summary.total_clients === 0) {
      return 0;
    }

    return Math.round((summary.compliant_clients / summary.total_clients) * 100);
  });
}
