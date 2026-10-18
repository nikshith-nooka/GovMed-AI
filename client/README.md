# GovMed-AI client

React + Vite interface for the benchmark results, case library and clinician workspace. The FastAPI server
(`src/api/server.py`) serves the production build from `client/dist`, which is committed so the Docker image
needs no Node toolchain.

```bash
npm ci
npm run dev      # development server; proxies /api to the backend
npm test         # Vitest + Testing Library
npm run lint
npm run build    # rebuild client/dist after any change to src/
```
