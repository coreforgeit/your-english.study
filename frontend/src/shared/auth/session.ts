import { readonly, shallowRef } from 'vue';

export type AuthenticatedSession = {
  readonly userId: number | null;
  readonly id: number;
};

const session = shallowRef<AuthenticatedSession | null>(null);
let nextSessionId = 0;
export const authenticatedSession = readonly(session);

export function clearAuthenticatedSession() {
  session.value = null;
}

export function startAuthenticatedSession(initData: string) {
  let userId: number | null = null;
  try {
    const user = JSON.parse(new URLSearchParams(initData).get('user') ?? 'null');
    if (user && Number.isSafeInteger(user.id) && user.id > 0) userId = user.id;
  } catch {
    // Не используем непроверенную локальную метку для авторизации.
    // При отсутствии id данные всё равно изолированы уникальным сеансом входа.
  }
  session.value = { userId, id: ++nextSessionId };
}

// startAuthenticatedSession вызывается только после подтверждения входа бэком.
// id — локальный идентификатор сеанса приложения, не cookie и не секрет.
