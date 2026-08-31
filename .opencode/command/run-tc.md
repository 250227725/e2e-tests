---
description: Изолированно запустить один реализованный Test Case
---

Используй:

- @.opencode/instructions/playwright-implementation.md
- @.opencode/instructions/diagnostics.md
- @.opencode/templates/completion-report.md

Целевой Test Case: `$1`.

Найди соответствующий spec-файл и запусти только этот TC. Не запускай проверочные TC и не изменяй код до завершения первичной диагностики.

Если запуск падает с ошибкой импорта модуля из `actions/` — см. диагностическую подсказку в `diagnostics.md` (устаревшая AA-зависимость после `/edit-aa`, требуется `/implement-tc`).
