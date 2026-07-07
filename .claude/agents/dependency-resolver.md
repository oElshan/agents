# Dependency Resolver Protocol

Shared-протокол для Team Leads. Определяет зависимости между issues и блокирует заблокированные карточки.

Хелперы доски (`kanban_query`, `kanban_set`, `kb_get`) требуют `source .claude/board.env` перед
использованием (см. `.claude/agents/kanban-board-sync.md`); если файла нет — остановись и сообщи
«запусти /init».

---

## Синтаксис зависимостей

В body issue используй одну из форм:

```
Blocked by: #10, #12
Depends on: #10
Requires: #10, #12, #15
```

Парсинг: regex `(?:Blocked by|Depends on|Requires):\s*(#\d+(?:\s*,\s*#\d+)*)` (case-insensitive).

---

## Алгоритм проверки

### Step 1 — Parse Dependencies

```
issue = mcp__github__get_issue(issue_number: N)
deps = parse_dependency_lines(issue.body)
```

Если `deps` пуст — issue **НЕ заблокирован**. Пропусти остальные шаги.

### Step 2 — Check Blocker State

Для каждого blocker `#M`:

```
blocker = mcp__github__get_issue(issue_number: M)
```

Blocker **resolved** если:
- `blocker.state == "closed"` ИЛИ
- Status блокера на доске == "Done" (`kanban_query "Done"` содержит #M)

Blocker **NOT resolved** если ни одно условие не выполнено.

### Step 3 — Verdict

- **Все** blockers resolved → issue **OK** (можно обрабатывать)
- **Хотя бы один** blocker NOT resolved → issue **BLOCKED**

### Step 4 — Circular Dependency Detection

При обходе зависимостей — отслеживай visited set. Если встретил уже visited issue — **CIRCULAR DEPENDENCY**.

Max depth: 10 уровней. Если depth > 10 — предупреди и считай BLOCKED.

---

## Формат вывода

### Если OK:
```
Dependencies for #{N}: OK
  #10 — closed ✅
  #12 — Status=Done ✅
```

### Если BLOCKED:
```
Dependencies for #{N}: BLOCKED 🚫
  #10 — closed ✅
  #12 — open, Status=In Development ❌ (BLOCKER)
  → Cannot proceed until #12 is resolved
```

### Если CIRCULAR:
```
Dependencies for #{N}: CIRCULAR DEPENDENCY ⚠️
  #N → #M → #K → #N (cycle detected)
  → Manual intervention required
```

---

## Интеграция с Team Leads

### analysis-lead
При создании stories — analyst ДОЛЖЕН добавить `Blocked by: #N` в body если story зависит от другой story или feature.

### dev-lead
**Перед spawn developer** — проверь dependencies каждой story:
1. Parse issue body
2. Check blocker state
3. Если BLOCKED — skip story, включи в BLOCKED секцию отчёта
4. Если OK — spawn developer

### qa-lead
**Перед spawn tester** — проверь dependencies:
1. Parse issue body
2. Check blocker state
3. Если BLOCKED — skip, report
4. Если OK — spawn tester + security-reviewer

---

## Auto-dispatch уведомления

Когда Team Lead переводит issue в "Done" (`kanban_set N "Done"`):
1. Найди issues которые зависят от закрытого:
   ```
   Grep issue bodies for "Blocked by: .*#{closed_issue}"
   ```
   (через `mcp__github__list_issues` + parse bodies)

2. Для каждого найденного — проверь все его blockers
3. Если ВСЕ blockers теперь resolved — добавь comment:
   ```
   🔓 **Unblocked**: All dependencies resolved.
   - #10 — closed ✅
   - #12 — closed ✅

   This issue is ready to proceed.
   ```

---

## Правила

1. **Dependency check = обязательный** перед запуском рабочего агента
2. **BLOCKED = skip** — не запускай агента, включи в BLOCKED секцию отчёта
3. **Circular = manual** — не пытайся автоматически разрешить цикл
4. **Max depth = 10** — защита от бесконечной рекурсии
5. **Минимум API calls** — кэшируй результаты get_issue в рамках одного прогона
