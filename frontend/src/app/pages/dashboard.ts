import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';

import { ClientTable } from '../components/client-table';
import { SummaryCards } from '../components/summary-cards';
import { Baseline, Client, ComplianceSummary } from '../models/inventory';
import { InventoryApi } from '../services/inventory-api';

const PAGE_SIZE = 25;

/**
 * The one page this application has.
 *
 * It owns all the state and all the loading; the two components below it are
 * presentational. That split is why their tests need no HTTP mock at all, and why this
 * test needs no DOM assertions about table cells.
 */
@Component({
  selector: 'app-dashboard',
  imports: [SummaryCards, ClientTable],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header>
      <h1>Client Inventory</h1>
      @if (baseline(); as rules) {
        <p class="baseline">
          Baseline: {{ rules.os_version_applies_to }} build {{ rules.minimum_os_version }} or newer,
          encryption {{ rules.require_encryption ? 'required' : 'optional' }}, patched within
          {{ rules.maximum_patch_age_days }} days, seen within
          {{ rules.maximum_last_seen_age_days }} days, at least
          {{ rules.minimum_disk_free_percent }}% disk free.
        </p>
      }
    </header>

    @if (errorMessage(); as message) {
      <p class="error" role="alert">{{ message }}</p>
    }

    @if (summary(); as counts) {
      <app-summary-cards [summary]="counts" />
    }

    <section class="controls">
      <label>
        <input type="checkbox" [checked]="onlyWithFindings()" (change)="toggleOnlyWithFindings()" />
        Only clients with findings
      </label>

      <span class="spacer"></span>

      <button type="button" [disabled]="!hasPreviousPage()" (click)="previousPage()">
        Previous
      </button>
      <span class="range">{{ rangeLabel() }}</span>
      <button type="button" [disabled]="!hasNextPage()" (click)="nextPage()">Next</button>
    </section>

    @if (loading()) {
      <p class="status">Loading…</p>
    }

    <app-client-table [clients]="clients()" />
  `,
  styles: `
    :host {
      display: block;
      max-width: 72rem;
      margin: 0 auto;
      padding: 1.5rem 1rem 3rem;
      font-family: system-ui, sans-serif;
      color: #1b1b1f;
    }

    h1 {
      font-size: 1.4rem;
      margin: 0 0 0.3rem;
    }

    .baseline {
      color: #55555c;
      font-size: 0.85rem;
      margin: 0 0 1.25rem;
      max-width: 56rem;
    }

    .controls {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem;
      margin: 1.25rem 0 0.75rem;
      font-size: 0.88rem;
    }

    .controls label {
      align-items: center;
      display: flex;
      gap: 0.4rem;
    }

    .spacer {
      flex: 1;
    }

    .range {
      font-variant-numeric: tabular-nums;
      color: #55555c;
    }

    button {
      background: #fff;
      border: 1px solid #c6c6cc;
      border-radius: 0.3rem;
      cursor: pointer;
      padding: 0.3rem 0.8rem;
    }

    button:disabled {
      color: #9a9aa2;
      cursor: default;
    }

    .error {
      background: #fdeceb;
      border-left: 4px solid #b3261e;
      margin: 0 0 1rem;
      padding: 0.6rem 0.8rem;
    }

    .status {
      color: #55555c;
      font-size: 0.85rem;
      margin: 0.5rem 0;
    }
  `,
})
export class Dashboard implements OnInit {
  private readonly api = inject(InventoryApi);

  readonly summary = signal<ComplianceSummary | null>(null);
  readonly baseline = signal<Baseline | null>(null);
  readonly clients = signal<readonly Client[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly onlyWithFindings = signal(false);
  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly hasPreviousPage = computed(() => this.offset() > 0);
  readonly hasNextPage = computed(() => this.offset() + PAGE_SIZE < this.total());

  /** "1-25 of 40", or a plain count when there is nothing to page through. */
  readonly rangeLabel = computed(() => {
    const total = this.total();
    if (total === 0) {
      return 'no clients';
    }

    const first = this.offset() + 1;
    const last = Math.min(this.offset() + PAGE_SIZE, total);

    return `${first}-${last} of ${total}`;
  });

  ngOnInit(): void {
    this.loadBaseline();
    this.loadSummary();
    this.loadClients();
  }

  /** Flip the filter and go back to the first page, since the result set changes. */
  toggleOnlyWithFindings(): void {
    this.onlyWithFindings.update((value) => !value);
    this.offset.set(0);
    this.loadClients();
  }

  nextPage(): void {
    if (!this.hasNextPage()) {
      return;
    }

    this.offset.update((value) => value + PAGE_SIZE);
    this.loadClients();
  }

  previousPage(): void {
    if (!this.hasPreviousPage()) {
      return;
    }

    this.offset.update((value) => Math.max(0, value - PAGE_SIZE));
    this.loadClients();
  }

  private loadClients(): void {
    this.loading.set(true);

    this.api
      .listClients({
        limit: PAGE_SIZE,
        offset: this.offset(),
        onlyWithFindings: this.onlyWithFindings(),
        osName: null,
      })
      .subscribe({
        next: (page) => {
          this.clients.set(page.items);
          this.total.set(page.total);
          this.loading.set(false);
        },
        error: () => {
          // The message names the service rather than echoing a status code: a reader of
          // this page cannot act on "500", but can act on "the API is not reachable".
          this.errorMessage.set('Could not reach the inventory API.');
          this.loading.set(false);
        },
      });
  }

  private loadSummary(): void {
    this.api.getSummary().subscribe({
      next: (summary) => this.summary.set(summary),
      error: () => this.errorMessage.set('Could not reach the inventory API.'),
    });
  }

  private loadBaseline(): void {
    this.api.getBaseline().subscribe({
      next: (baseline) => this.baseline.set(baseline),
      // A missing baseline only costs the explanatory line, so it is not worth an alert.
      error: () => this.baseline.set(null),
    });
  }
}
