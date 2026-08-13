<script setup lang="ts">
import { Check, ChevronDown, Clock3 } from '@lucide/vue';
import { nextTick, ref, watch } from 'vue';

const ITEM_HEIGHT = 44;

const props = defineProps<{
  modelValue: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const hours = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0'));
const minutes = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, '0'));
const isOpen = ref(false);
const draftHour = ref('20');
const draftMinute = ref('00');
const hourWheel = ref<HTMLElement | null>(null);
const minuteWheel = ref<HTMLElement | null>(null);
let hourAnimationFrame: number | null = null;
let minuteAnimationFrame: number | null = null;

function parseTime(value: string) {
  const [hour = '20', minute = '00'] = value.split(':');
  return {
    hour: hours.includes(hour) ? hour : '20',
    minute: minutes.includes(minute) ? minute : '00',
  };
}

function scrollToValue(element: HTMLElement | null, values: string[], value: string, behavior: ScrollBehavior) {
  const index = Math.max(values.indexOf(value), 0);
  element?.scrollTo({ top: index * ITEM_HEIGHT, behavior });
}

async function openPicker() {
  if (props.disabled) {
    return;
  }

  const time = parseTime(props.modelValue);
  draftHour.value = time.hour;
  draftMinute.value = time.minute;
  isOpen.value = true;
  await nextTick();
  scrollToValue(hourWheel.value, hours, draftHour.value, 'auto');
  scrollToValue(minuteWheel.value, minutes, draftMinute.value, 'auto');
}

function closePicker() {
  isOpen.value = false;
}

function confirmTime() {
  emit('update:modelValue', `${draftHour.value}:${draftMinute.value}`);
  closePicker();
}

function selectValue(type: 'hour' | 'minute', value: string) {
  if (type === 'hour') {
    draftHour.value = value;
    scrollToValue(hourWheel.value, hours, value, 'smooth');
    return;
  }

  draftMinute.value = value;
  scrollToValue(minuteWheel.value, minutes, value, 'smooth');
}

function updateValueFromScroll(type: 'hour' | 'minute') {
  const element = type === 'hour' ? hourWheel.value : minuteWheel.value;
  const values = type === 'hour' ? hours : minutes;
  const frame = type === 'hour' ? hourAnimationFrame : minuteAnimationFrame;

  if (frame !== null) {
    cancelAnimationFrame(frame);
  }

  const nextFrame = requestAnimationFrame(() => {
    if (!element) {
      return;
    }

    const index = Math.min(Math.max(Math.round(element.scrollTop / ITEM_HEIGHT), 0), values.length - 1);
    if (type === 'hour') {
      draftHour.value = values[index];
      hourAnimationFrame = null;
    } else {
      draftMinute.value = values[index];
      minuteAnimationFrame = null;
    }
  });

  if (type === 'hour') {
    hourAnimationFrame = nextFrame;
  } else {
    minuteAnimationFrame = nextFrame;
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (isOpen.value) {
      return;
    }

    const time = parseTime(value);
    draftHour.value = time.hour;
    draftMinute.value = time.minute;
  },
  { immediate: true },
);
</script>

<template>
  <button class="time-picker-trigger" type="button" :disabled="disabled" @click="openPicker">
    <Clock3 :size="20" />
    <span>{{ modelValue }}</span>
    <ChevronDown :size="18" />
  </button>

  <Teleport to="body">
    <div v-if="isOpen" class="time-picker-backdrop" @click.self="closePicker">
      <section class="time-picker-sheet" role="dialog" aria-modal="true" aria-labelledby="time-picker-title">
        <header class="time-picker-header">
          <button type="button" @click="closePicker">Отмена</button>
          <h3 id="time-picker-title">Время напоминания</h3>
          <button class="time-picker-done" type="button" @click="confirmTime">
            <Check :size="18" />
            Готово
          </button>
        </header>

        <div class="time-picker-wheels">
          <div class="time-picker-selection" aria-hidden="true"></div>

          <div
            ref="hourWheel"
            class="time-picker-wheel"
            role="listbox"
            aria-label="Часы"
            :aria-activedescendant="`time-hour-${draftHour}`"
            @scroll.passive="updateValueFromScroll('hour')"
          >
            <button
              v-for="hour in hours"
              :id="`time-hour-${hour}`"
              :key="hour"
              type="button"
              role="option"
              :aria-selected="draftHour === hour"
              :class="{ active: draftHour === hour }"
              @click="selectValue('hour', hour)"
            >
              {{ hour }}
            </button>
          </div>

          <span class="time-picker-colon" aria-hidden="true">:</span>

          <div
            ref="minuteWheel"
            class="time-picker-wheel"
            role="listbox"
            aria-label="Минуты"
            :aria-activedescendant="`time-minute-${draftMinute}`"
            @scroll.passive="updateValueFromScroll('minute')"
          >
            <button
              v-for="minute in minutes"
              :id="`time-minute-${minute}`"
              :key="minute"
              type="button"
              role="option"
              :aria-selected="draftMinute === minute"
              :class="{ active: draftMinute === minute }"
              @click="selectValue('minute', minute)"
            >
              {{ minute }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.time-picker-trigger {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 48px;
  padding: 0 13px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-background);
  color: var(--color-text);
  cursor: pointer;
  font-size: 17px;
  font-variant-numeric: tabular-nums;
  font-weight: 800;
  text-align: left;
}

.time-picker-trigger svg:first-child {
  color: var(--color-primary-text);
}

.time-picker-trigger svg:last-child {
  color: var(--color-text-muted);
}

.time-picker-trigger:disabled {
  cursor: default;
  opacity: 0.55;
}

.time-picker-backdrop {
  position: fixed;
  z-index: 100;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: var(--color-backdrop);
}

.time-picker-sheet {
  width: min(100%, 380px);
  padding: 8px 16px 20px;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: var(--color-surface);
  box-shadow: 0 18px 50px var(--color-shadow-strong);
  animation: time-picker-enter 180ms ease-out;
}

.time-picker-header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: 52px;
  border-bottom: 1px solid var(--color-border);
}

.time-picker-header h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 16px;
  text-align: center;
}

.time-picker-header button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 0;
  border: 0;
  background: var(--color-transparent);
  color: var(--color-primary-text);
  cursor: pointer;
  font-weight: 700;
}

.time-picker-header .time-picker-done {
  justify-self: end;
  font-weight: 800;
}

.time-picker-wheels {
  position: relative;
  display: grid;
  grid-template-columns: minmax(72px, 112px) 24px minmax(72px, 112px);
  justify-content: center;
  height: 220px;
  overflow: hidden;
}

.time-picker-wheels::before,
.time-picker-wheels::after {
  position: absolute;
  z-index: 3;
  right: 0;
  left: 0;
  height: 72px;
  content: '';
  pointer-events: none;
}

.time-picker-wheels::before {
  top: 0;
  background: linear-gradient(var(--color-surface), var(--color-transparent));
}

.time-picker-wheels::after {
  bottom: 0;
  background: linear-gradient(var(--color-transparent), var(--color-surface));
}

.time-picker-selection {
  position: absolute;
  z-index: 0;
  top: 88px;
  right: 12%;
  left: 12%;
  height: 44px;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-primary-soft);
  pointer-events: none;
}

.time-picker-wheel {
  position: relative;
  z-index: 1;
  height: 220px;
  padding: 88px 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: none;
  scroll-snap-type: y mandatory;
  overscroll-behavior: contain;
}

.time-picker-wheel::-webkit-scrollbar {
  display: none;
}

.time-picker-wheel button {
  display: block;
  width: 100%;
  height: 44px;
  padding: 0;
  border: 0;
  background: var(--color-transparent);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 21px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  opacity: 0.55;
  scroll-snap-align: center;
}

.time-picker-wheel button.active {
  color: var(--color-text);
  font-size: 24px;
  font-weight: 800;
  opacity: 1;
}

.time-picker-colon {
  position: relative;
  z-index: 2;
  align-self: center;
  color: var(--color-text);
  font-size: 24px;
  font-weight: 800;
  text-align: center;
  transform: translateY(-1px);
}

@keyframes time-picker-enter {
  from {
    opacity: 0;
    transform: scale(0.96);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
