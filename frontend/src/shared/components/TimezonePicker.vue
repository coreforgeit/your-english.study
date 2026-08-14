<script setup lang="ts">
import { ChevronDown, Globe2 } from '@lucide/vue';
import { computed, ref, watch } from 'vue';

type TimezoneOption = {
  name: string;
  group: string[];
  currentTimeOffsetInMinutes: number;
  currentTimeFormat: string;
};

const props = defineProps<{
  modelValue: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const allTimezoneOptions = ref<TimezoneOption[]>([]);
const isLoading = ref(false);
let loadPromise: Promise<void> | null = null;

function getNativeOffsetLabel(timezone: string) {
  try {
    const offset = new Intl.DateTimeFormat('en', {
      timeZone: timezone,
      timeZoneName: 'longOffset',
    })
      .formatToParts(new Date())
      .find((part) => part.type === 'timeZoneName')?.value;
    return offset?.replace('GMT', '') || '+00:00';
  } catch {
    return '';
  }
}

async function loadTimezoneOptions() {
  if (allTimezoneOptions.value.length > 0) {
    return;
  }
  if (loadPromise) {
    return loadPromise;
  }

  isLoading.value = true;
  loadPromise = import('@vvo/tzdb')
    .then(({ getTimeZones }) => {
      allTimezoneOptions.value = getTimeZones({ includeUtc: true });
    })
    .catch(() => {
      // Keep the detected IANA value available if the optional data chunk fails to load.
    })
    .finally(() => {
      isLoading.value = false;
      loadPromise = null;
    });

  return loadPromise;
}

const timezoneOptions = computed(() => {
  const groupedTimezones = new Map<number, TimezoneOption[]>();

  for (const timezone of allTimezoneOptions.value) {
    const group = groupedTimezones.get(timezone.currentTimeOffsetInMinutes) ?? [];
    group.push(timezone);
    groupedTimezones.set(timezone.currentTimeOffsetInMinutes, group);
  }

  return [...groupedTimezones.entries()]
    .sort(([leftOffset], [rightOffset]) => leftOffset - rightOffset)
    .map(([offset, timezones]) => {
      if (offset === 180) {
        return timezones.find((timezone) => timezone.name === 'Europe/Moscow') ?? timezones[0];
      }

      if (offset === 0) {
        return timezones.find((timezone) => timezone.name === 'Etc/UTC') ?? timezones[0];
      }

      return (
        timezones.find(
          (timezone) =>
            timezone.name === props.modelValue || timezone.group.includes(props.modelValue),
        ) ?? timezones[0]
      );
    });
});

const selectedOffset = computed(
  () =>
    allTimezoneOptions.value.find(
      (timezone) => timezone.name === props.modelValue || timezone.group.includes(props.modelValue),
    )?.currentTimeOffsetInMinutes ?? null,
);

const displayOptions = computed(() =>
  timezoneOptions.value.map((timezone) => ({
    value: timezone.currentTimeOffsetInMinutes === selectedOffset.value ? props.modelValue : timezone.name,
    label: timezone.currentTimeFormat,
    offset: timezone.currentTimeOffsetInMinutes,
  })),
);

const hasSelectedOption = computed(() =>
  displayOptions.value.some((timezone) => timezone.value === props.modelValue),
);

const fallbackLabel = computed(() => {
  const offset = getNativeOffsetLabel(props.modelValue);
  return `${offset} ${props.modelValue}`.trim();
});

const selectedTimezone = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

watch(
  () => props.modelValue,
  () => void loadTimezoneOptions(),
  { immediate: true },
);
</script>

<template>
  <div class="timezone-select" :class="{ disabled: disabled || isLoading }">
    <Globe2 :size="20" />
    <select
      v-model="selectedTimezone"
      :disabled="disabled || isLoading"
      aria-label="Часовой пояс"
    >
      <option v-if="!hasSelectedOption" :value="modelValue">
        {{ isLoading ? 'Loading time zones…' : fallbackLabel }}
      </option>
      <option
        v-for="timezoneOption in displayOptions"
        :key="timezoneOption.offset"
        :value="timezoneOption.value"
      >
        {{ timezoneOption.label }}
      </option>
    </select>
    <ChevronDown :size="18" />
  </div>
</template>

<style scoped>
.timezone-select {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 48px;
  padding: 0 13px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-background);
  color: var(--color-text);
}

.timezone-select:focus-within {
  border-color: var(--color-accent);
}

.timezone-select > svg:first-child {
  color: var(--color-primary-text);
}

.timezone-select > svg:last-child {
  z-index: 1;
  grid-column: 3;
  grid-row: 1;
  justify-self: end;
  color: var(--color-text-muted);
  pointer-events: none;
}

.timezone-select select {
  grid-column: 2 / 4;
  grid-row: 1;
  width: 100%;
  min-width: 0;
  height: 46px;
  padding: 0 28px 0 0;
  overflow: hidden;
  border: 0;
  outline: 0;
  appearance: none;
  background: var(--color-transparent);
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timezone-select.disabled {
  opacity: 0.55;
}

.timezone-select select:disabled {
  cursor: default;
}
</style>
