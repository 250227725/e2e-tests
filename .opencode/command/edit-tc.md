---
description: Интерактивно изменить существующую спецификацию Test Case
---

Используй правила из @AGENTS.md, @.opencode/instructions/documentation-authoring.md и @.opencode/instructions/playwright-implementation.md.
Используй структуру @.opencode/templates/test-case.md.

Целевой Test Case: `$1`.

1. Загрузи текущую утверждённую редакцию `docs/test-cases/TC-<CODE>-<NNN>.md`, покажи пользователю.
2. Веди диалог изменений по правилам «Интерактивного режима» из `documentation-authoring.md` (батчинг вопросов 3–5).
3. После согласования новой редакции подготовь полный текст и передай его через stdin в `python3 .opencode/scripts/document_authoring.py validate --kind tc --id TC-<CODE>-<NNN> --content-file - --mode update`.
4. Покажи полный прошедший проверку текст, запроси явное подтверждение именно этой редакции.
5. После подтверждения, но до записи: вычисли новый хэш (`document_authoring.py hash --kind tc --id TC-<CODE>-<NNN>`), сравни с хэшем в существующем файле теста (если файла нет — пропусти этот шаг). При любом расхождении удали файл теста и `TC-<...>.selectors.json` целиком — по `playwright-implementation.md`, раздел «Редактирование Action и TC» → «`/edit-tc`».
6. Выполни удаление, определённое на шаге 5, **до** записи новой редакции документа.
7. Передай тот же текст в `python3 .opencode/scripts/document_authoring.py update --kind tc --id TC-<CODE>-<NNN> --content-file -`.
8. Сообщи: что изменено, была ли удалена реализация, что потребуется повторный `/implement-tc`.

Не создавай новые TC/Action. Не изменяй документы, не являющиеся целью редактирования.
