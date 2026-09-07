---
description: Интерактивно создать новую спецификацию Test Case
---

Используй @.opencode/instructions/documentation-authoring.md и @.opencode/templates/test-case.md.

Начальное описание пользователя:

$ARGUMENTS

Создай ровно один новый TC.

1. Выполни `python3 .opencode/scripts/document_authoring.py inventory --kind tc` и `python3 .opencode/scripts/document_authoring.py inventory --kind aa`.
2. Собери недостающие сведения в диалоге, по правилам «Интерактивного режима» из `documentation-authoring.md`.
3. Согласуй с пользователем идентификатор целиком, по правилам формирования ID из `documentation-authoring.md` («Формирование Test Case» → «Идентификатор»): домен + `_` + английский kebab-case slug, перифразирующий «Условие проверки». Идентификатор: `TC-<ДОМЕН>_<slug>`, целевой путь: `docs/test-cases/TC-<ДОМЕН>_<slug>.md`. Уникальность — по результату `inventory` из шага 1, автоматической нумерации нет.
4. Подготовь полный текст и передай его через stdin в `python3 .opencode/scripts/document_authoring.py validate --kind tc --id <ID> --content-file -`.
5. Покажи целевой путь и полный прошедший проверку текст, затем запроси явное подтверждение.
6. Только после подтверждения передай тот же текст в `python3 .opencode/scripts/document_authoring.py create --kind tc --id <ID> --content-file -`.

Если необходимого Action нет, не создавай его автоматически. Не записывай документ другими средствами и не создавай другие файлы.
