import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Client } from '../models/inventory';
import { ClientTable } from './client-table';

const NOW = new Date('2026-10-27T12:00:00Z');

function client(overrides: Partial<Client> = {}): Client {
  return {
    hostname: 'ws-0001',
    os_name: 'Windows',
    os_version: '10.0.26100.1742',
    agent_version: '1.4.2',
    encryption_enabled: true,
    disk_total_gb: 512,
    disk_free_gb: 256,
    free_disk_percent: 50,
    last_patched_at: '2026-10-24T12:00:00Z',
    first_seen_at: '2026-09-01T12:00:00Z',
    last_seen_at: '2026-10-27T06:00:00Z',
    compliant: true,
    findings: [],
    ...overrides,
  };
}

describe('ClientTable', () => {
  let fixture: ComponentFixture<ClientTable>;

  async function render(clients: readonly Client[]): Promise<HTMLElement> {
    fixture = TestBed.createComponent(ClientTable);
    fixture.componentRef.setInput('clients', clients);
    fixture.componentRef.setInput('now', NOW);
    await fixture.whenStable();

    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ClientTable] }).compileComponents();
  });

  it('renders one row per client', async () => {
    const element = await render([client(), client({ hostname: 'ws-0002' })]);

    expect(element.querySelectorAll('tbody tr')).toHaveLength(2);
  });

  it('says so when the filter matches nothing', async () => {
    const element = await render([]);

    expect(element.textContent).toContain('No clients match the current filter.');
  });

  it('marks a compliant client as such instead of listing findings', async () => {
    const element = await render([client()]);

    expect(element.querySelector('.badge.ok')?.textContent?.trim()).toBe('compliant');
    expect(element.querySelectorAll('.findings li')).toHaveLength(0);
  });

  it('lists every finding with its severity', async () => {
    const element = await render([
      client({
        compliant: false,
        findings: [
          { code: 'os_version_below_baseline', severity: 'high', detail: 'Build too old.' },
          { code: 'not_seen_recently', severity: 'medium', detail: 'Last seen 46 days ago.' },
        ],
      }),
    ]);

    // The badge and the label are separate elements spaced by CSS, so they are asserted
    // separately rather than through the concatenated text content.
    const findings = [...element.querySelectorAll('.findings li')].map((row) => ({
      severity: row.querySelector('.badge')?.textContent?.trim(),
      label: row.querySelector('span[title]')?.textContent?.trim(),
    }));

    expect(findings).toEqual([
      { severity: 'high', label: 'os version below baseline' },
      { severity: 'medium', label: 'not seen recently' },
    ]);
  });

  it('keeps the detail text as the title, so the table stays narrow', async () => {
    const element = await render([
      client({
        compliant: false,
        findings: [{ code: 'disk_space_low', severity: 'low', detail: '3.9 percent free.' }],
      }),
    ]);

    expect(element.querySelector('.findings li span[title]')?.getAttribute('title')).toBe(
      '3.9 percent free.',
    );
  });

  it('renders a code it has never seen rather than an empty cell', async () => {
    // A newer backend can add a rule; the table should still be readable.
    const element = await render([
      client({
        compliant: false,
        findings: [{ code: 'tpm_not_present', severity: 'high', detail: 'No TPM.' }],
      }),
    ]);

    expect(element.textContent).toContain('tpm not present');
  });

  it('shows the age of the last check-in in words', async () => {
    const element = await render([client({ last_seen_at: '2026-09-11T00:00:00Z' })]);

    expect(element.textContent).toContain('46 days ago');
  });

  it('shows unknown when the API could not work out the free space', async () => {
    const element = await render([client({ free_disk_percent: null })]);

    expect(element.textContent).toContain('unknown');
  });
});
