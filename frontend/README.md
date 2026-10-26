# Frontend

The Angular dashboard for the Client Inventory API. The project README one level up
explains what the whole thing is for; this file is only the commands.

```bash
npm install
npm start              # dev server on http://localhost:4200
npm test               # 40 tests on Vitest with jsdom, no browser needed
npm run lint
npm run typecheck
npm run format         # or format:check, which is what CI runs
npm run build
```

The dashboard expects the API at `http://127.0.0.1:8000`, which is set as `API_BASE_URL`
in `src/app/app.config.ts`. Served from the same origin as the API, that value becomes an
empty string.
