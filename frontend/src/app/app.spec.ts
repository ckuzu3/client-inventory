import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { App } from './app';
import { API_BASE_URL } from './services/api-config';

const BASE_URL = 'http://api.test';

describe('App', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: BASE_URL },
      ],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
  });

  it('mounts the dashboard', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();

    // The shell's whole job is to render the one page, so that is what is asserted.
    expect((fixture.nativeElement as HTMLElement).querySelector('app-dashboard')).not.toBeNull();

    http
      .match(() => true)
      .forEach((request) => request.flush({}, { status: 204, statusText: 'No Content' }));
  });
});
