# System Design Checklist (SDC) — 8 обязательных слотов

Единый чек-лист системных вопросов. **analyst** заполняет слоты в spec, **architect**
детализирует в arch doc, **code-reviewer (java)** сверяет код со слотами (SDC-01..SDC-07),
**qa-lead** проверяет TC-покрытие слотов 2/5/8, **ops-lead** — слоты 4/7 на G8,
**postdeploy.sh** — слот 7 через 72ч после prod.

Стек-агностичен: конкретные технологии (БД, брокер, k8s) берутся из `.claude/project-profile.md`.

## Когда обязателен

- `Type=feature` — всегда
- `Size=l` / `Size=xl` — всегда
- Изменение shared-contracts модуля (`topology.shared_contracts` из профиля) — всегда
- Новая DB-миграция — всегда (слоты 4 + 7)
- Новый external call (HTTP/gRPC к другому сервису или третьей стороне) — всегда (слот 5)
- Новая очередь/exchange/topic — всегда
- Новый микросервис или новый Deployment в k8s — всегда (все слоты)

**НЕ обязателен:** `Size=xs`/`s` локально в одном модуле, без новых таблиц/очередей/external.
В spec одна строка: `SDC: N/A — локальный рефакторинг`.

## Слоты

### 1. OWNERSHIP
- Кто владеет данными (owner-модуль/сервис из `.claude/system/ownership-map.md`)?
- Кто consumers? Tenant-scope (если multi-tenant)?
- Cross-service запись ТОЛЬКО через API/event владельца — прямой доступ к чужой БД запрещён.

### 2. IDEMPOTENCY
- Что при повторной доставке сообщения / повторном вызове API / retry клиента?
- Где живёт idempotency key (заголовок, таблица, unique constraint)?
- Для consumers: at-least-once — как дедуплицируем?

### 3. CONSISTENCY
- Граница транзакции (какие таблицы в одной транзакции)?
- Кросс-сервисная согласованность: паттерн (saga / outbox / eventual + reconciliation)?
- Какой инвариант защищаем и что его нарушает?

### 4. MIGRATION
- Forward-скрипт + backward (rollback) или forward-only с обоснованием.
- Совместимость: старый код + новая схема должны жить вместе на время rolling update в k8s
  (expand → migrate → contract).
- Данные: объём, время миграции, блокировки (для high-load — online-миграция без table lock).

### 5. RESILIENCE
- Для КАЖДОГО external call: timeout (connect + read), retry-политика (сколько, backoff),
  circuit breaker (имя, пороги), fallback.
- Что происходит при недоступности зависимости — degrade или fail fast?
- k8s: readiness должен отражать доступность критических зависимостей? (обычно НЕТ — иначе каскад)

### 6. BLAST RADIUS
- Затронутые DTO/Events/API-контракты + список consumers **с grep evidence**.
- breaking / non-breaking. Если breaking — стратегия версионирования (v2 endpoint, новая
  версия схемы event, dual-write период).
- Затронутые k8s-объекты (Deployment/ConfigMap/Secret/HPA).

### 7. PROD AC (production acceptance criteria)
- Latency p95/p99 цель, error rate порог, throughput (RPS) — ЦИФРЫ, не «быстро».
- Idempotency assertion (как проверить в проде).
- Kill switch: feature flag / env var / ConfigMap-ключ, которым фича выключается БЕЗ redeploy.
- Как метрики читаются: имена метрик Prometheus (или иного из `infra.monitoring`).

### 8. NOT-DOING (anti-scope)
- Что СОЗНАТЕЛЬНО не делаем и почему.
- Что станет tech-debt issue (создать сразу с `Type=tech-debt`).

## Формат в spec

```markdown
## SDC
| # | Слот | Решение |
|---|------|---------|
| 1 | OWNERSHIP | order-service владеет `orders`; consumers: billing (event OrderCreated) |
| 2 | IDEMPOTENCY | Idempotency-Key header + unique(orders.external_id) |
| 3 | CONSISTENCY | Одна транзакция orders+order_items; billing — через outbox |
| 4 | MIGRATION | V42__add_orders.sql + rollback в arch doc; expand-contract |
| 5 | RESILIENCE | billing-client: timeout 2s/5s, retry 2×backoff, CB `billingCB` 50%/10s |
| 6 | BLAST RADIUS | OrderDto: +field optional → non-breaking; consumers: grep-список |
| 7 | PROD AC | p95 < 200ms, err < 0.1%, 300 RPS; kill switch: `features.order-v2` |
| 8 | NOT-DOING | Без пересчёта историй заказов (tech-debt #NNN) |
```
