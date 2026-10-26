import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Baseline, Client, ClientPage, ComplianceSummary } from '../models/inventory';
import { API_BASE_URL } from '../services/api-config';
import { Dashboard } from './dashboard';

const BASE_URL = 'http://api.test';

const BASELINE: Baseline = {
  minimum_os_version: '10.0.26100',
  os_version_applies_to: 'Windows',
  require_encryption: true,
  maximum_patch_age_days: 35,
  maximum_last_seen_age_days: 14,
  minimum_disk_free_percent: 10,
};

const SUMMARY: ComplianceSummary = {
  evaluated_at: '2026-10-27T12:00:00Z',
  total_clients: 40,
  compliant_clients: 3,
  noncompliant_clients: 37,
  findings_by_code: { encryption_disabled: 8 },
  findings_by_severity: { high: 8 },
};

function client(hostname: string): Client {
  return {
    hostname,
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
  };
}

function page(overrides: Partial<ClientPage> = {}): ClientPage {
  return { items: [client('ws-0001')], total: 40, limit: 25, offset: 0, ...overrides };
}

describe('Dashboard', () => {
  let fixture: ComponentFixture<Dashboard>;
  let http: HttpTestingController;

  /** Answer the three requests the page makes on load. */
  function answerInitialLoad(clientPage: ClientPage = page()): void {
    http.expectOne(`${BASE_URL}/api/v1/baseline`).flush(BASELINE);
    http.expectOne(`${BASE_URL}/api/v1/compliance/summary`).flush(SUMMARY);
    clientRequest().flush(clientPage);
  }

  function clientRequest() {
    return http.expectOne((candidate) => candidate.url === `${BASE_URL}/api/v1/clients`);
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: BASE_URL },
      ],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Dashboard);
  });

  afterEach(() => {
    http.verify();
  });

  it('loads the baseline, the summary and the first page on startup', async () => {
    await fixture.whenStable();
    answerInitialLoad();
    await fixture.whenStable();

    expect(fixture.componentInstance.clients()).toHaveLength(1);
    expect(fixture.componentInstance.total()).toBe(40);
    expect(fixture.componentInstance.loading()).toBe(false);
  });

  it('states the baseline in words, so a reader knows what is being measured', async () => {
    await fixture.whenStable();
    answerInitialLoad();
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('build 10.0.26100 or newer');
    expect(text).toContain('encryption required');
  });

  it('labels the visible range', async () => {
    await fixture.whenStable();
    answerInitialLoad();
    await fixture.whenStable();

    expect(fixture.componentInstance.rangeLabel()).toBe('1-25 of 40');
  });

  it('says there are no clients instead of showing an empty range', async () => {
    await fixture.whenStable();
    answerInitialLoad(page({ items: [], total: 0 }));
    await fixture.whenStable();

    expect(fixture.componentInstance.rangeLabel()).toBe('no clients');
  });

  it('pages forward and asks the API for the next offset', async () => {
    await fixture.whenStable();
    answerInitialLoad();
    await fixture.whenStable();

    fixture.componentInstance.nextPage();
    const request = clientRequest();

    expect(request.request.params.get('offset')).toBe('25');
    request.flush(page({ items: [client('ws-0026')], offset: 25 }));
    await fixture.whenStable();

    expect(fixture.componentInstance.hasPreviousPage()).toBe(true);
  });

  it('cannot page past the end', async () => {
    await fixture.whenStable();
    answerInitialLoad(page({ total: 10 }));
    await fixture.whenStable();

    expect(fixture.componentInstance.hasNextPage()).toBe(false);

    // No further request is made, which http.verify() in afterEach confirms.
    fixture.componentInstance.nextPage();

    expect(fixture.componentInstance.offset()).toBe(0);
  });

  it('cannot page before the beginning', async () => {
    await fixture.whenStable();
    answerInitialLoad();
    await fixture.whenStable();

    fixture.componentInstance.previousPage();

    expect(fixture.componentInstance.offset()).toBe(0);
  });

  it('returns to the first page when the filter changes', async () => {
    await fixture.whenStable();
    answerInitialLoad();
    await fixture.whenStable();

    fixture.componentInstance.nextPage();
    clientRequest().flush(page({ offset: 25 }));
    await fixture.whenStable();

    fixture.componentInstance.toggleOnlyWithFindings();
    const request = clientRequest();

    // A different filter means a different result set, so page three of the old one is
    // meaningless.
    expect(request.request.params.get('offset')).toBe('0');
    expect(request.request.params.get('only_with_findings')).toBe('true');
    request.flush(page({ total: 37 }));
  });

  it('tells the reader when the API cannot be reached', async () => {
    await fixture.whenStable();
    http.expectOne(`${BASE_URL}/api/v1/baseline`).flush(BASELINE);
    http.expectOne(`${BASE_URL}/api/v1/compliance/summary`).flush(SUMMARY);
    clientRequest().error(new ProgressEvent('network error'));
    await fixture.whenStable();

    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');

    expect(alert?.textContent).toContain('Could not reach the inventory API.');
    expect(fixture.componentInstance.loading()).toBe(false);
  });

  it('still renders the page when only the baseline is unavailable', async () => {
    await fixture.whenStable();
    http.expectOne(`${BASE_URL}/api/v1/baseline`).error(new ProgressEvent('network error'));
    http.expectOne(`${BASE_URL}/api/v1/compliance/summary`).flush(SUMMARY);
    clientRequest().flush(page());
    await fixture.whenStable();

    // A missing baseline costs the explanatory line and nothing else, so it is not an alert.
    expect(fixture.componentInstance.baseline()).toBeNull();
    expect(fixture.componentInstance.errorMessage()).toBeNull();
    expect(fixture.componentInstance.clients()).toHaveLength(1);
  });
});
