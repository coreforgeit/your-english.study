import { readonly, ref } from 'vue';

import type { NotificationMessage } from '@/shared/api/notifications';

export type NotificationListItem = NotificationMessage & { id: number };

const messages = ref<NotificationListItem[]>([]);
let nextMessageId = 0;

export function useNotificationCenter() {
  function addNotification(notification: NotificationMessage) {
    messages.value = [
      {
        id: ++nextMessageId,
        ...notification,
      },
      ...messages.value,
    ];
  }

  function clearNotifications() {
    messages.value = [];
  }

  // Один центр объединяет сообщения SSE и локальные события интерфейса.
  return {
    messages: readonly(messages),
    addNotification,
    clearNotifications,
  };
}
