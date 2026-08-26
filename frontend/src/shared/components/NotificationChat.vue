<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

type NotificationChatMessage = {
  id: number;
  type: 'word_status_changed';
  word: string;
  status: 'new' | 'familiar' | 'learned';
};

function getStatusLabel(status: NotificationChatMessage['status']): string {
  switch (status) {
    case 'new':
      return 'новое';
    case 'familiar':
      return 'знакомое';
    case 'learned':
      return 'изучено';
  }
}

const props = defineProps<{
  messages: NotificationChatMessage[];
  withNavigation?: boolean;
}>();

const messageList = ref<HTMLElement | null>(null);

watch(
  () => props.messages.length,
  async () => {
    await nextTick();
    messageList.value?.scrollTo({ top: 0, behavior: 'smooth' });
  },
);
</script>

<template>
  <aside
    v-if="messages.length"
    class="notification-chat"
    :class="{ 'notification-chat-with-navigation': withNavigation }"
    aria-label="SSE-сообщения"
  >
    <header class="notification-chat-header">
      <h2>Сообщения</h2>
      <span class="notification-chat-badge">SSE</span>
    </header>

    <ol
      ref="messageList"
      class="notification-chat-list"
      aria-live="polite"
      aria-relevant="additions"
    >
      <li v-for="message in messages" :key="message.id" class="notification-chat-message">
        <span>Статус слова изменён</span>
        <strong>«{{ message.word }}»: {{ getStatusLabel(message.status) }}</strong>
      </li>
    </ol>
  </aside>
</template>

<style scoped>
.notification-chat {
  position: fixed;
  z-index: 25;
  right: calc(12px + env(safe-area-inset-right));
  bottom: calc(12px + env(safe-area-inset-bottom));
  display: grid;
  width: min(280px, calc(100vw - 24px));
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  box-shadow: 0 8px 24px var(--color-shadow-soft);
}

.notification-chat-with-navigation {
  bottom: calc(
    var(--bottom-navigation-height) + 132px + env(safe-area-inset-bottom)
  );
}

.notification-chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 44px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.notification-chat-header h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 800;
}

.notification-chat-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--color-success-soft);
  color: var(--color-success-text);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.notification-chat-list {
  display: grid;
  gap: 8px;
  max-height: calc(5 * 40px + 4 * 8px + 20px);
  margin: 0;
  padding: 10px;
  overflow-y: auto;
  overscroll-behavior: contain;
  list-style: none;
  scrollbar-color: var(--color-primary-strong) var(--color-neutral-soft);
  scrollbar-width: thin;
}

.notification-chat-list::-webkit-scrollbar {
  width: 6px;
}

.notification-chat-list::-webkit-scrollbar-track {
  border-radius: 999px;
  background: var(--color-neutral-soft);
}

.notification-chat-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: var(--color-primary-strong);
}

.notification-chat-message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--color-primary-strong);
  border-radius: 12px 12px 4px 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
}

.notification-chat-message span {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 12px;
  font-weight: 700;
}

.notification-chat-message strong {
  min-width: 0;
  color: var(--color-text);
  font-size: 14px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
</style>
