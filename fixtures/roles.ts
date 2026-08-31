// fixtures/roles.ts — генерируется и поддерживается /configure-roles, не редактировать вручную.
// Значения ROLE_STATE_PATHS — прямая копия поля «Файл состояния» из docs/roles.md для каждой роли.

const ROLE_STATE_PATHS: Record<string, string> = {
  // Заполняется автоматически при первом /configure-roles.
};

export function roleStorageState(code: string): string {
  const path = ROLE_STATE_PATHS[code];
  if (!path) {
    throw new Error(`Неизвестная роль: ${code}. Проверьте docs/roles.md и выполните /configure-roles при необходимости.`);
  }
  return path;
}
