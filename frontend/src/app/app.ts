import { Component } from '@angular/core';

import { Dashboard } from './pages/dashboard';

/**
 * The application shell.
 *
 * There is one page, so there is no router. An empty `Routes` array and a
 * `<router-outlet>` with nothing to put in it would be dead code, and the moment a
 * second page exists the router can be added with the change it belongs to.
 */
@Component({
  selector: 'app-root',
  imports: [Dashboard],
  template: '<app-dashboard />',
})
export class App {}
