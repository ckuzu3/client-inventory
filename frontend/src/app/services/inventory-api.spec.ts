import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ClientPage } from '../models/inventory';
import { API_BASE_URL } from './api-config';
import { InventoryApi } from './inventory-api';

const BASE_URL = 'http://api.test';

describe('InventoryApi', () => {
  let api: InventoryApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: BASE_URL },
      ],
    });

    api = TestBed.inject(InventoryApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('requests a page with the limit and offset it was given', () => {
    api.listClients({ limit: 25, offset: 50, onlyWithFindings: false, osName: null }).subscribe();

    const request = http.expectOne((candidate) => candidate.url === `${BASE_URL}/api/v1/clients`);

    expect(request.request.params.get('limit')).toBe('25');
    expect(request.request.params.get('offset')).toBe('50');
    request.flush({ items: [], total: 0, limit: 25, offset: 50 } satisfies ClientPage);
  });

  it('leaves unset filters out of the query string', () => {
    // Sending os_name= would ask for clients whose operating system is the empty
    // string, which is a different question from "no filter".
    api.listClients({ limit: 10, offset: 0, onlyWithFindings: false, osName: null }).subscribe();

    const request = http.expectOne((candidate) => candidate.url === `${BASE_URL}/api/v1/clients`);

    expect(request.request.params.has('os_name')).toBe(false);
    expect(request.request.params.has('only_with_findings')).toBe(false);
    request.flush({ items: [], total: 0, limit: 10, offset: 0 } satisfies ClientPage);
  });

  it('sends the filters that are set', () => {
    api
      .listClients({ limit: 10, offset: 0, onlyWithFindings: true, osName: 'Windows' })
      .subscribe();

    const request = http.expectOne((candidate) => candidate.url === `${BASE_URL}/api/v1/clients`);

    expect(request.request.params.get('only_with_findings')).toBe('true');
    expect(request.request.params.get('os_name')).toBe('Windows');
    request.flush({ items: [], total: 0, limit: 10, offset: 0 } satisfies ClientPage);
  });

  it('returns the page the API sent', () => {
    const page: ClientPage = {
      items: [],
      total: 7,
      limit: 25,
      offset: 0,
    };
    let received: ClientPage | undefined;

    api
      .listClients({ limit: 25, offset: 0, onlyWithFindings: false, osName: null })
      .subscribe((value) => (received = value));
    http.expectOne((candidate) => candidate.url === `${BASE_URL}/api/v1/clients`).flush(page);

    expect(received?.total).toBe(7);
  });

  it('reads the summary from the versioned path', () => {
    api.getSummary().subscribe();

    const request = http.expectOne(`${BASE_URL}/api/v1/compliance/summary`);

    expect(request.request.method).toBe('GET');
    request.flush({
      evaluated_at: '2026-10-27T12:00:00Z',
      total_clients: 0,
      compliant_clients: 0,
      noncompliant_clients: 0,
      findings_by_code: {},
      findings_by_severity: {},
    });
  });

  it('reads the baseline from the versioned path', () => {
    api.getBaseline().subscribe();

    const request = http.expectOne(`${BASE_URL}/api/v1/baseline`);

    expect(request.request.method).toBe('GET');
    request.flush({
      minimum_os_version: '10.0.26100',
      os_version_applies_to: 'Windows',
      require_encryption: true,
      maximum_patch_age_days: 35,
      maximum_last_seen_age_days: 14,
      minimum_disk_free_percent: 10,
    });
  });
});
