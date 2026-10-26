import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { Client } from '../models/inventory';
import { describeAge } from '../shared/relative-time';

/**
 * The worklist.
 *
 * Also presentational: the parent decides what to load and in which order, this renders
 * it. The API already sorts the longest-silent client first, so there is no sorting here
 * to disagree with the backend about.
 */
@Component({
  selector: 'app-client-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <table>
      <caption class="sr-only">
        Managed clients and the baseline rules they fail
      </caption>
      <thead>
        <tr>
          <th scope="col">Hostname</th>
          <th scope="col">Operating system</th>
          <th scope="col">Last seen</th>
          <th scope="col">Free disk</th>
          <th scope="col">Findings</th>
        </tr>
      </thead>
      <tbody>
        @for (client of clients(); track client.hostname) {
          <tr [class.attention]="!client.compliant">
            <td class="hostname">{{ client.hostname }}</td>
            <td>{{ client.os_name }} {{ client.os_version }}</td>
            <td>{{ age(client) }}</td>
            <td class="numeric">
              @if (client.free_disk_percent !== null) {
                {{ client.free_disk_percent }}%
              } @else {
                unknown
              }
            </td>
            <td>
              @if (client.compliant) {
                <span class="badge ok">compliant</span>
              } @else {
                <ul class="findings">
                  @for (finding of client.findings; track finding.code) {
                    <li>
                      <span class="badge {{ finding.severity }}">{{ finding.severity }}</span>
                      <span [title]="finding.detail">{{ label(finding.code) }}</span>
                    </li>
                  }
                </ul>
              }
            </td>
          </tr>
        } @empty {
          <tr>
            <td colspan="5" class="empty">No clients match the current filter.</td>
          </tr>
        }
      </tbody>
    </table>
  `,
  styles: `
    table {
      border-collapse: collapse;
      width: 100%;
      background: #fff;
      border: 1px solid #e2e2e6;
      border-radius: 0.5rem;
      font-size: 0.88rem;
    }

    th,
    td {
      border-bottom: 1px solid #ededf0;
      padding: 0.5rem 0.75rem;
      text-align: left;
      vertical-align: top;
    }

    th {
      background: #f7f7f9;
      font-size: 0.74rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #55555c;
    }

    tr.attention .hostname {
      font-weight: 600;
    }

    .numeric {
      font-variant-numeric: tabular-nums;
    }

    .findings {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .findings li {
      display: flex;
      gap: 0.4rem;
      align-items: baseline;
    }

    .empty {
      color: #55555c;
      padding: 1.25rem 0.75rem;
      text-align: center;
    }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip-path: inset(50%);
    }
  `,
})
export class ClientTable {
  /** The page of clients to render. */
  readonly clients = input.required<readonly Client[]>();

  /** The moment ages are measured against, injected so the rendered text is testable. */
  readonly now = input<Date>(new Date());

  /** A short age label for the last check-in. */
  age(client: Client): string {
    return describeAge(client.last_seen_at, this.now());
  }

  /**
   * Turn a finding code into something readable.
   *
   * An unknown code from a newer backend still renders, just with its raw underscores
   * replaced, instead of showing an empty cell.
   */
  label(code: string): string {
    return code.replace(/_/g, ' ');
  }
}
