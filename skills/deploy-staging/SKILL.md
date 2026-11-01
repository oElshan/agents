---
name: deploy-staging
description: Деплой проверенных артефактов на staging. Проверка SHA, digest, rollout, health, smoke, логов и отката. Код и конфигурация неизменны.
---

# Деплой на staging

Только staging. Команды бери из `.agents/profile.md`. Пустая обязательная команда
даёт BLOCKED. Ошибка команды блокирует PASS. Не пересобирай артефакты во время деплоя.

## 1. Проверки до деплоя

- HEAD равен SHA из задачи, дерево чистое.
- Manifest из G7 содержит этот SHA и digest каждого артефакта.
- Команда staging использует digest из manifest, а не изменяемый тег.
- Если `quality.high_load: true`, проверь манифесты затронутых сервисов
  (`stack.infra.k8s_manifests_path`): заданы requests и limits, readiness и liveness, replicas ≥ 2
  у критичных сервисов, HPA там, где он заявлен в arch doc. Нарушение: FAIL до деплоя.

Нужна правка файла: BLOCKED. Верни список правок. Они должны пройти разработку, ревью и QA.

## 2. Деплой и раскатка

Выполни `commands.deploy.staging`, затем `commands.deploy.status`.
Обе команды должны завершиться с кодом 0. Используй staging context и namespace из профиля.
Проверь каждый сервис из manifest. Не используй текущий контекст Kubernetes без проверки.

## 3. Health, smoke и логи

Для каждого затронутого сервиса:

```bash
python3 .opencode/lib/gates.py health --url <staging-url><health>
```

Затем выполни `commands.smoke.staging`. Код 0 обязателен.
Пример получения и проверки логов Kubernetes:

```bash
python3 .opencode/lib/gates.py logs -- kubectl --context <staging-context> logs deployment/<service> -n <staging-namespace> --since=60s
```

Для Compose передай после `--` команду `docker compose logs --since=60s <service>`.
Код 0 = логи получены, заданные признаки ошибок не найдены. Код 1 = найдены признаки
`error`, `exception` или `fatal`. Код 2 = логи не получены. Код 2 нельзя назвать «чисто».
При коде 2 верни BLOCKED. При коде 1 верни FAIL.
Проверка ищет текстовые признаки; она не подтверждает полноту журналов всех реплик.

Health или smoke упал: выполни настроенный откат и проверь его результат. Итог FAIL.
Команда отката отсутствует или завершилась ошибкой: остановись и сообщи об этом.

## 4. Репетиция отката

Если задан `commands.deploy.rollback` и SDC 4 не `forward-only`:
1. выполни откат, проверь rollout;
2. проверь health и, если миграция обратима, состояние схемы;
3. верни те же артефакты повторным `<commands.deploy.staging>`, без новой сборки;
4. повтори rollout, health, smoke и проверку логов.

Нет команды отката или forward-only: `skipped` с этой причиной.

## 5. Kill switch

Если SDC 7 заявляет kill switch: переключи его (флаг, env, ключ ConfigMap), покажи эффект
(лог, ответ endpoint, метрика), верни обратно. Не меняй файлы проекта.
После возврата повтори health и smoke.

## 6. Проверка артефактов

После всех действий:

```bash
python3 .opencode/lib/gates.py artifact --verified <SHA из G7> --command '<commands.deploy.observe_artifact>' --expected <artifact_manifest_sha>
```

Команда наблюдения читает фактические digest и версию кода из staging. Она возвращает JSON
с полями `commit` и `artifacts`. Формат описан в `.opencode/lib/README.md`.
Проверка сверяет manifest, HEAD и чистоту дерева. Только PASS разрешает G8.

## 7. Отчёт

По формату из промпта devops: каждая строка с реальным выводом команды.
