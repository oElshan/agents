# Агентная команда · v2.1.0

Пакет для OpenCode. Содержит 10 агентов, команды, правила процесса и исполняемые проверки.
Нужны Git, Bash и Python 3.9+. Загрузка агентов проверена на OpenCode 2.2.5.

- [Подключение и описание продукта](https://github.com/oElshan/agents#readme)
- [Проверки и переход с версии 1.x](lib/README.md)
- [Шаблон профиля](skills/project-setup/templates/profile.md)
- [Правила процесса](framework.md)
- [Master → story → correction и миграция спек](skills/write-spec/references/spec-graph.md)
- [Параллельные stories в worktree](skills/parallel-stories/SKILL.md)

При обновлении с 2.0 сохраните старые specs, настройте parallel_stories через /setup и
перенесите активные фичи на master + story по инструкции миграции. Старые утверждённые
файлы не переписывайте; новые контракты проходят G2 и approve. Без нового поля профиля
работа остаётся последовательной.

При обновлении с 1.x замените настройку CSV на `coverage_sources` с JaCoCo XML.
Для staging настройте команды подготовки и наблюдения артефактов.
Для активных фич повторите G2 и утверждение документов.

Проверка установленного пакета из корня проекта:

```bash
cat .opencode/VERSION
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .opencode/tests -q
```

Полный цикл агентов и staging с новыми проверками пока не подтверждён.
Политики не заменяют файловую изоляцию. Вызов проверок пока обеспечивает оркестратор.
