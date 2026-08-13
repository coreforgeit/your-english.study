<script setup lang="ts">
import { Check, ChevronDown, Globe2, Search, X } from '@lucide/vue';
import { computed, nextTick, ref } from 'vue';

type TimezoneOption = {
  name: string;
  alternativeName: string;
  group: string[];
  countryName: string;
  countryCode: string;
  mainCities: string[];
  currentTimeOffsetInMinutes: number;
  localizedName: string;
  localizedCountry: string;
  offsetLabel: string;
  searchText: string;
};

const props = defineProps<{
  modelValue: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const searchQuery = ref('');
const isOpen = ref(false);
const isLoading = ref(false);
const loadError = ref<string | null>(null);
const searchInput = ref<HTMLInputElement | null>(null);
const timezoneOptions = ref<TimezoneOption[]>([]);
const regionNames = new Intl.DisplayNames(['ru'], { type: 'region' });

function getLocalizedName(timezone: string) {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: timezone,
      timeZoneName: 'longGeneric',
    })
      .formatToParts(new Date())
      .find((part) => part.type === 'timeZoneName')?.value;
  } catch {
    return null;
  }
}

function formatOffset(offsetInMinutes: number) {
  const sign = offsetInMinutes >= 0 ? '+' : '-';
  const absoluteOffset = Math.abs(offsetInMinutes);
  const hours = String(Math.floor(absoluteOffset / 60)).padStart(2, '0');
  const minutes = String(absoluteOffset % 60).padStart(2, '0');
  return `UTC${sign}${hours}:${minutes}`;
}

function getNativeOffsetLabel(timezone: string) {
  try {
    const offset = new Intl.DateTimeFormat('en', {
      timeZone: timezone,
      timeZoneName: 'longOffset',
    })
      .formatToParts(new Date())
      .find((part) => part.type === 'timeZoneName')?.value;
    return offset?.replace('GMT', 'UTC') ?? null;
  } catch {
    return null;
  }
}

async function loadTimezoneOptions() {
  if (timezoneOptions.value.length > 0 || isLoading.value) {
    return;
  }

  isLoading.value = true;
  loadError.value = null;

  try {
    const { getTimeZones } = await import('@vvo/tzdb');
    timezoneOptions.value = getTimeZones({ includeUtc: true }).map((timezone) => {
      const fallbackName = timezone.mainCities[0] ?? timezone.alternativeName ?? timezone.name;
      const localizedName = getLocalizedName(timezone.name) ?? fallbackName;
      const localizedCountry = regionNames.of(timezone.countryCode) ?? timezone.countryName;

      return {
        ...timezone,
        localizedName,
        localizedCountry,
        offsetLabel: formatOffset(timezone.currentTimeOffsetInMinutes),
        searchText: [
          localizedName,
          localizedCountry,
          timezone.name,
          timezone.alternativeName,
          timezone.countryName,
          ...timezone.mainCities,
          ...timezone.group,
        ]
          .join(' ')
          .toLocaleLowerCase('ru-RU'),
      };
    });
  } catch {
    loadError.value = 'Не удалось загрузить часовые пояса.';
  } finally {
    isLoading.value = false;
  }
}

const selectedTimezone = computed(
  () =>
    timezoneOptions.value.find(
      (timezone) => timezone.name === props.modelValue || timezone.group.includes(props.modelValue),
    ) ?? null,
);

const triggerLabel = computed(() => {
  const timezone = selectedTimezone.value;
  if (!timezone) {
    const name = getLocalizedName(props.modelValue) ?? props.modelValue;
    const offset = getNativeOffsetLabel(props.modelValue);
    return offset ? `${name} · ${offset}` : name;
  }
  return `${timezone.localizedName} · ${timezone.offsetLabel}`;
});

const filteredTimezones = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase('ru-RU');
  if (!query) {
    return timezoneOptions.value;
  }
  return timezoneOptions.value.filter((timezone) => timezone.searchText.includes(query));
});

async function openPicker() {
  if (props.disabled) {
    return;
  }

  searchQuery.value = '';
  isOpen.value = true;
  await nextTick();
  searchInput.value?.focus();
  await loadTimezoneOptions();
  await nextTick();
  document.querySelector<HTMLElement>('.timezone-option.active')?.scrollIntoView({ block: 'center' });
}

function closePicker() {
  isOpen.value = false;
}

function selectTimezone(timezone: TimezoneOption) {
  emit('update:modelValue', timezone.name);
  closePicker();
}
</script>

<template>
  <button class="timezone-picker-trigger" type="button" :disabled="disabled" @click="openPicker">
    <Globe2 :size="20" />
    <span>{{ triggerLabel }}</span>
    <ChevronDown :size="18" />
  </button>

  <Teleport to="body">
    <div v-if="isOpen" class="timezone-picker-backdrop" @click.self="closePicker">
      <section
        class="timezone-picker-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="timezone-picker-title"
      >
        <header class="timezone-picker-header">
          <div>
            <h3 id="timezone-picker-title">Часовой пояс</h3>
            <p>Выберите город или регион</p>
          </div>
          <button type="button" aria-label="Закрыть" @click="closePicker">
            <X :size="21" />
          </button>
        </header>

        <label class="timezone-search">
          <Search :size="19" />
          <input ref="searchInput" v-model="searchQuery" type="search" placeholder="Поиск" />
        </label>

        <div class="timezone-options" role="listbox" aria-label="Часовые пояса">
          <p v-if="isLoading" class="timezone-empty">Загружаем часовые пояса…</p>

          <p v-else-if="loadError" class="timezone-empty timezone-load-error">
            {{ loadError }}
          </p>

          <button
            v-for="timezoneOption in filteredTimezones"
            :key="timezoneOption.name"
            class="timezone-option"
            :class="{ active: timezoneOption === selectedTimezone }"
            type="button"
            role="option"
            :aria-selected="timezoneOption === selectedTimezone"
            @click="selectTimezone(timezoneOption)"
          >
            <span class="timezone-option-main">
              <strong>{{ timezoneOption.localizedName }}</strong>
              <small>{{ timezoneOption.localizedCountry }} · {{ timezoneOption.name }}</small>
            </span>
            <span class="timezone-option-offset">{{ timezoneOption.offsetLabel }}</span>
            <Check v-if="timezoneOption === selectedTimezone" :size="20" />
          </button>

          <p v-if="!isLoading && !loadError && filteredTimezones.length === 0" class="timezone-empty">
            Ничего не найдено
          </p>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.timezone-picker-trigger {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 48px;
  padding: 8px 13px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-background);
  color: var(--color-text);
  cursor: pointer;
  font-weight: 700;
  text-align: left;
}

.timezone-picker-trigger span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timezone-picker-trigger svg:first-child {
  color: var(--color-primary-text);
}

.timezone-picker-trigger svg:last-child {
  color: var(--color-text-muted);
}

.timezone-picker-trigger:disabled {
  cursor: default;
  opacity: 0.55;
}

.timezone-picker-backdrop {
  position: fixed;
  z-index: 100;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: var(--color-backdrop);
}

.timezone-picker-dialog {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 14px;
  width: min(100%, 440px);
  height: min(680px, calc(100dvh - 40px));
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: var(--color-surface);
  box-shadow: 0 18px 50px var(--color-shadow-strong);
  animation: timezone-picker-enter 180ms ease-out;
}

.timezone-picker-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.timezone-picker-header h3,
.timezone-picker-header p {
  margin: 0;
}

.timezone-picker-header h3 {
  font-size: 20px;
}

.timezone-picker-header p {
  margin-top: 3px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.timezone-picker-header button {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: var(--color-neutral-soft);
  color: var(--color-neutral-text);
  cursor: pointer;
}

.timezone-search {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 9px;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-background);
  color: var(--color-text-muted);
}

.timezone-search:focus-within {
  border-color: var(--color-accent);
}

.timezone-search input {
  min-width: 0;
  height: 42px;
  padding: 0;
  border: 0;
  outline: 0;
  background: var(--color-transparent);
  color: var(--color-text);
  font: inherit;
}

.timezone-options {
  min-height: 0;
  overflow-y: auto;
  border-top: 1px solid var(--color-border);
}

.timezone-option {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 20px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 62px;
  padding: 9px 6px;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-transparent);
  color: var(--color-text);
  cursor: pointer;
  text-align: left;
}

.timezone-option:hover,
.timezone-option:focus,
.timezone-option.active {
  background: var(--color-primary-soft);
}

.timezone-option-main {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.timezone-option-main strong,
.timezone-option-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timezone-option-main strong {
  font-size: 14px;
}

.timezone-option-main small {
  color: var(--color-text-muted);
  font-size: 11px;
}

.timezone-option-offset {
  color: var(--color-primary-text);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 800;
}

.timezone-option > svg {
  color: var(--color-primary-text);
}

.timezone-empty {
  margin: 32px 0;
  color: var(--color-text-muted);
  text-align: center;
}

.timezone-load-error {
  color: var(--color-danger-text);
}

@keyframes timezone-picker-enter {
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
