import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Baseline, ClientPage, ClientQuery, ComplianceSummary } from '../models/inventory';
import { API_BASE_URL } from './api-config';

/**
 * The only place in the frontend that knows an HTTP API exists.
 *
 * Components receive data and render it; nothing else builds a URL or a query string.
 * That keeps the components testable with plain objects and means a change to the API
 * surface has one file to change.
 */
@Injectable({ providedIn: 'root' })
export class InventoryApi {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  /** Fetch one page of clients. */
  listClients(query: ClientQuery): Observable<ClientPage> {
    let params = new HttpParams().set('limit', query.limit).set('offset', query.offset);

    // Only send the filters that are actually set. Sending `os_name=` would ask the API
    // for clients whose operating system is the empty string, which is not the same
    // question as "no filter".
    if (query.onlyWithFindings) {
      params = params.set('only_with_findings', true);
    }

    if (query.osName) {
      params = params.set('os_name', query.osName);
    }

    return this.http.get<ClientPage>(`${this.baseUrl}/api/v1/clients`, { params });
  }

  /** Fetch the fleet-wide counts. */
  getSummary(): Observable<ComplianceSummary> {
    return this.http.get<ComplianceSummary>(`${this.baseUrl}/api/v1/compliance/summary`);
  }

  /** Fetch the rules the fleet is measured against. */
  getBaseline(): Observable<Baseline> {
    return this.http.get<Baseline>(`${this.baseUrl}/api/v1/baseline`);
  }
}
