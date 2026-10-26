import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ComplianceSummary } from '../models/inventory';
import { SummaryCards } from './summary-cards';

function summary(overrides: Partial<ComplianceSummary> = {}): ComplianceSummary {
  return {
    evaluated_at: '2026-10-27T12:00:00Z',
    total_clients: 40,
    compliant_clients: 10,
    noncompliant_clients: 30,
    findings_by_code: { encryption_disabled: 8, disk_space_low: 16 },
    findings_by_severity: { high: 8, low: 16, medium: 23 },
    ...overrides,
  };
}

describe('SummaryCards', () => {
  let fixture: ComponentFixture<SummaryCards>;

  async function render(value: ComplianceSummary): Promise<HTMLElement> {
    fixture = TestBed.createComponent(SummaryCards);
    fixture.componentRef.setInput('summary', value);
    await fixture.whenStable();

    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [SummaryCards] }).compileComponents();
  });

  it('shows the three headline figures', async () => {
    const element = await render(summary());
    const figures = [...element.querySelectorAll('.figure')].map((node) =>
      node.textContent?.trim(),
    );

    expect(figures).toEqual(['40', '10', '30']);
  });

  it('works out the compliant share', async () => {
    await render(summary());

    expect(fixture.componentInstance.compliantPercent()).toBe(25);
  });

  it('reports zero rather than dividing by zero for an empty fleet', async () => {
    await render(summary({ total_clients: 0, compliant_clients: 0, noncompliant_clients: 0 }));

    expect(fixture.componentInstance.compliantPercent()).toBe(0);
  });

  it('orders the severities worst first, whatever order the API used', async () => {
    await render(summary());
    const severities = fixture.componentInstance.severityCounts().map((entry) => entry.severity);

    expect(severities).toEqual(['high', 'medium', 'low']);
  });

  it('leaves out a severity that has no findings', async () => {
    await render(summary({ findings_by_severity: { high: 2 } }));
    const severities = fixture.componentInstance.severityCounts().map((entry) => entry.severity);

    expect(severities).toEqual(['high']);
  });

  it('adds up the findings across severities', async () => {
    await render(summary());

    expect(fixture.componentInstance.totalFindings()).toBe(47);
  });

  it('says so when a clean fleet has nothing to report', async () => {
    const element = await render(summary({ findings_by_severity: {} }));

    expect(element.textContent).toContain('Nothing to report.');
  });
});
