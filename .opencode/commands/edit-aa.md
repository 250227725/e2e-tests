---
description: Интерактивно изменить существующую спецификацию Atomic Action
---

Используй правила из @AGENTS.md, @.opencode/instructions/documentation-authoring.md и @.opencode/instructions/playwright-implementation.md.
Используй структуру @.opencode/templates/atomic-action.md.

Целевой Atomic Action: `$1`.

1. Загрузи текущую утверждённую редакцию `docs/atomic-actions/AA-<CODE>.md`, покажи пользователю.
2. Веди диалог изменений по правилам «Интерактивного режима» из `documentation-authoring.md` (батчинг вопросов 3–5).
3. После согласования новой редакции подготовь полный текст и передай его через stdin в `python3 .opencode/scripts/document_authoring.py validate --kind aa --id AA-<CODE> --content-file - --mode update`.
4. Покажи полный прошедший проверку текст, запроси явное подтверждение именно этой редакции.
5. После подтверждения, но до записи: вычисли новые хэши (`document_authoring.py hash --kind aa --id AA-<CODE> --part signature` и `--part logic`), сравни с хэшами в существующем `actions/AA-<CODE>.ts` (если файла нет — пропусти этот шаг). Определи тип изменения и последствия по `playwright-implementation.md`, раздел «Редактирование AA и TC» → «`/edit-aa`»: удаление реализации самой AA и, при смене сигнатуры, реализаций зависимых TC (найденных через `document_authoring.py dependents --kind aa --id AA-<CODE>`).
6. Выполни удаления, определённые на шаге 5, **до** записи новой редакции документа.
7. Передай тот же текст в `python3 .opencode/scripts/document_authoring.py update --kind aa --id AA-<CODE> --content-file -`.
8. Сообщи: что изменено, какой тип изменения (сигнатура/логика/назначение), какие файлы удалены, какие TC потребуют повторного `/implement-tc`.

Не создавай новые TC/AA. Не изменяй документы, не являющиеся целью редактирования.
