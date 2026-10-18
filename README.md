# meihua-metaphysics

梅花易数 US daily cast service, the two lookup tables, and the 花椒短线 integration that calls it.

The four 齐济 volumes and their page-text extracts are not in this repository. `knowledge_base/qiji_64x64.json` is the extracted table: 4096 keys, 4082 verdicts from the 1996 book, 14 keys left empty because that scan had no matching entry.

## Service

From this directory:

```bash
PYTHONPATH=. python3 -m engine.server
```

- `GET /v1/health`
- `POST /v1/cast/daily`
- `POST /v1/cast/question`

Printed prices for sectors come from `data/2026_us_daily.csv`. The symbol list is `dashboard/sectors.json`. Rules are `knowledge_base/meihua_64x6.json` (384 cells).

## Docs

- `docs/梅花日频预测引擎设计.md`
- `docs/玄学板块-PRD.md`
- `docs/玄学板块-技术组件.md`
- `docs/玄学板块-架构.md`

## 花椒短线 integration

`huajiao/` is the metaphysics slice of the shortline app, not the whole app.

- `backend/src/api/mod.rs` registers `GET /api/us/metaphysics/daily` and `POST /api/us/metaphysics/question` on `api::router()`, which sits behind `subscription_gate`.
- `backend/src/api/us/metaphysics.rs` proxies those routes to the Python service.
- `backend/migrations/0059_metaphysics_question_quota.sql` is the Shanghai-calendar-day question quota.
- `frontend/src/views/us/metaphysics.jsx` plus the `us-meihua-daily` and `us-meihua-question` registrations.
- `frontend/public/sw.js` does not cache `/api/us/metaphysics/`.
- `deploy/docker-compose.yml` adds a `meihua` service with no host port mapping. `MEIHUA_URL` is `http://meihua:8090`. Passwords in that file are `${...}` references, not values.
- `meihua/Dockerfile` is the image used by that service. Its `COPY` paths expect `meihua/engine`, `meihua/knowledge_base`, and `meihua/data` inside the shortline build context. Those trees in the running app are this repo's `engine/`, `knowledge_base/`, and `data/`.
