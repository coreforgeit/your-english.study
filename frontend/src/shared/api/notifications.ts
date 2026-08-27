import { z } from 'zod';

import { BACKEND_URL } from '@/shared/config';

const notificationSchema = z.object({
  type: z.enum([
    'five_new_words_today',
    'ten_new_words_today',
    'word_status_changed',
    'word_learned',
  ]),
  text: z.string().min(1),
});

export type NotificationMessage = z.infer<typeof notificationSchema>;

export function createNotificationStream(
  onNotification: (notification: NotificationMessage) => void,
): EventSource {
  const eventSource = new EventSource(
    `${BACKEND_URL}/api/telegram-app/notifications/stream`,
    { withCredentials: true },
  );

  eventSource.addEventListener('notification', (event) => {
    const rawData = (event as MessageEvent<string>).data;
    let parsedData: unknown;
    try {
      parsedData = JSON.parse(rawData);
    } catch {
      return;
    }

    const result = notificationSchema.safeParse(parsedData);
    if (result.success) {
      onNotification(result.data);
    }
  });

  return eventSource;
}
