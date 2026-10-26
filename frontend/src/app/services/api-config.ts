import { InjectionToken } from '@angular/core';

/**
 * Where the API lives.
 *
 * An injection token rather than a constant import, so the value is provided once in
 * `app.config.ts` and a test can point the service somewhere else without touching the
 * code under test.
 */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  factory: () => 'http://127.0.0.1:8000',
});
