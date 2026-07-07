---
description: "Kanban: Feature. Создать Feature Request. Примеры: /feature Bulk Export данных | /feature Интеграция с внешним API"
argument-hint: "<описание фичи на естественном языке>"
---

# KANBAN — Feature Request: $ARGUMENTS

Ты выступаешь в роли **Senior Product Analyst**. Создай качественный Feature Request в GitHub Issues.

## Алгоритм (АВТОНОМНО)

### 1. Понимание контекста
```
Read(".claude/project-profile.md")  # ПЕРВЫМ: стек (stack.*) и топология (topology.services) — какие сервисы затрагивает фича; если initialized: false — Fallback Detect из профиля
Read("CLAUDE.md")
Read("ARCHITECTURE.md")  # если есть
```
Изучи текущий стек, архитектуру, ограничения проекта и топологию: по `topology.services`
из профиля определи, какие сервисы/приложения затрагивает фича.

### 2. Проверка дубликатов

Доска — источник правды; фильтрация по лейблам ЗАПРЕЩЕНА (хелперы из `.claude/agents/kanban-board-sync.md`):
```bash
kb_dump | jq -r '.[] | select(.type=="feature" and .status!="Done") | "#\(.number)\t\(.title)"'
```
Проверь что аналогичной фичи нет в backlog.

### 3. Создание Feature Request Issue

```
mcp__github__create_issue(
  title: "[FEATURE] {краткое название}",
  body: "## Описание фичи\n{что и зачем}\n\n## Бизнес-ценность\n{какую проблему решает, кому полезно}\n\n## Пользовательские сценарии\n- **Как** {роль}\n- **Я хочу** {действие}\n- **Чтобы** {результат}\n\n## Acceptance Criteria (высокоуровневые)\n- [ ] {критерий 1}\n- [ ] {критерий 2}\n- [ ] {критерий 3}\n\n## Затронутые компоненты\n- [ ] Backend\n- [ ] Frontend\n- [ ] AI\n- [ ] Infrastructure\n\n## Зависимости\n{от чего зависит или что блокирует}\n\n## Оценка сложности\n- **Размер**: XS / S / M / L / XL\n- **Риски**: {технические и бизнес-риски}\n\n---\n_Created via /feature command_"
)
```

> Чек-лист «Затронутые компоненты» в body — иллюстрация для читателя issue; фактическое
> множество компонент — значения **Component-поля доски** (backend, frontend, ai, infra,
> docs, qa), они записываются через `kb_meta`, не лейблами.

Затем положи issue на доску в колонку Backlog и заполни поля (лейблы при создании НЕ ставятся):
```
kanban_set {number} "Backlog"   # хелпер из .claude/agents/kanban-board-sync.md
kb_meta {number} type=feature priority={level} size={est} component={csv}   # метаданные = поля доски
```

### 4. Определи приоритет (поле Priority доски)
- `critical` — блокирует ключевые цели
- `high` — ключевая бизнес-функция
- `medium` — полезное улучшение
- `low` — nice-to-have

Записывается: `kb_meta {number} priority={level}`.

### 5. Определи размер (поле Size доски)
- `xs` (< 2ч) → `s` (пол-дня) → `m` (1-2 дня) → `l` (3-5 дней) → `xl` (1+ неделя)

Записывается: `kb_meta {number} size={est}`.

### 6. Заполни поле Component (text, CSV — не лейблы)
- Значения: `backend`, `frontend`, `ai`, `infra` (+ `docs`, `qa` при необходимости) — сверяйся с `topology.services` из профиля, какие сервисы затрагивает фича
- Записывается: `kb_meta {number} component=backend,frontend`

## Финальный отчёт
```
FEATURE REQUEST CREATED
Issue: #{number} — {title}
Priority: {priority}
Size: {size}
Component: {csv}   # всё — поля доски, лейблы не используются
Column: Backlog
Next step: /analyze #{number}
```
