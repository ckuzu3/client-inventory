import { provideHttpClient, withFetch } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';

import { API_BASE_URL } from './services/api-config';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(withFetch()),
    // Provided here rather than imported from a constant, so a different deployment
    // overrides one value. Served from the same origin as the API, this becomes ''.
    { provide: API_BASE_URL, useValue: 'http://127.0.0.1:8000' },
  ],
};
