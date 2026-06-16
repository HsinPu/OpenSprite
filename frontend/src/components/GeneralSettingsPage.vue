<template>
  <section class="settings-page">
    <div class="settings-card">
      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.language.title }}</strong>
          <span>{{ copy.settings.general.language.description }}</span>
        </div>
        <select v-model="form.language" :aria-label="copy.settings.general.language.title">
          <option value="zh-TW">{{ copy.settings.general.language.options.zhTW }}</option>
          <option value="en">{{ copy.settings.general.language.options.en }}</option>
        </select>
      </div>

      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.workState.title }}</strong>
          <span>{{ copy.settings.general.workState.description }}</span>
        </div>
        <input v-model="form.showWorkState" class="switch" type="checkbox" :aria-label="copy.settings.general.workState.title" />
      </div>

      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.runHistory.title }}</strong>
          <span>{{ copy.settings.general.runHistory.description }}</span>
        </div>
        <input v-model="form.showRunHistory" class="switch" type="checkbox" :aria-label="copy.settings.general.runHistory.title" />
      </div>

      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.runTimeline.title }}</strong>
          <span>{{ copy.settings.general.runTimeline.description }}</span>
        </div>
        <input v-model="form.showRunTimeline" class="switch" type="checkbox" :aria-label="copy.settings.general.runTimeline.title" />
      </div>

      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.runSummary.title }}</strong>
          <span>{{ copy.settings.general.runSummary.description }}</span>
        </div>
        <input v-model="form.showRunSummary" class="switch" type="checkbox" :aria-label="copy.settings.general.runSummary.title" />
      </div>

      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.runTrace.title }}</strong>
          <span>{{ copy.settings.general.runTrace.description }}</span>
        </div>
        <input v-model="form.showRunTrace" class="switch" type="checkbox" :aria-label="copy.settings.general.runTrace.title" />
      </div>
    </div>

    <h3>{{ copy.settings.general.connectionTitle }}</h3>
    <div class="settings-card settings-card--form">
      <label class="settings-row settings-row--field">
        <div>
          <strong>{{ copy.settings.general.wsUrl.title }}</strong>
          <span>{{ copy.settings.general.wsUrl.description }}</span>
        </div>
        <input v-model="form.wsUrl" type="text" spellcheck="false" @change="$emit('save-connection-settings')" />
      </label>

      <label class="settings-row settings-row--field">
        <div>
          <strong>{{ copy.settings.general.accessToken.title }}</strong>
          <span>{{ copy.settings.general.accessToken.description }}</span>
        </div>
        <input v-model="form.accessToken" type="password" autocomplete="current-password" spellcheck="false" @change="$emit('save-connection-settings')" />
      </label>

      <label class="settings-row settings-row--field">
        <div>
          <strong>{{ copy.settings.general.displayName.title }}</strong>
          <span>{{ copy.settings.general.displayName.description }}</span>
        </div>
        <input v-model="form.displayName" type="text" maxlength="60" @change="$emit('save-connection-settings')" />
      </label>

      <label class="settings-row settings-row--field">
        <div>
          <strong>{{ copy.settings.general.externalChatId.title }}</strong>
          <span>{{ copy.settings.general.externalChatId.description }}</span>
        </div>
        <input v-model="form.externalChatId" type="text" spellcheck="false" @change="$emit('save-connection-settings')" />
      </label>

      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.gateway.title }}</strong>
          <span>{{ connectionSwitchLabel }}</span>
        </div>
        <input
          class="switch"
          type="checkbox"
          :aria-label="copy.settings.general.gateway.title"
          :checked="connectionSwitchChecked"
          :disabled="connectionState === 'connecting'"
          @change="$emit('toggle-connection', $event.target.checked)"
        />
      </div>
    </div>

    <h3>{{ copy.settings.general.appearanceTitle }}</h3>
    <div class="settings-card">
      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.general.colorScheme.title }}</strong>
          <span>{{ copy.settings.general.colorScheme.description }}</span>
        </div>
        <select v-model="form.colorScheme" :aria-label="copy.settings.general.colorScheme.title">
          <option value="system">{{ copy.settings.general.colorScheme.options.system }}</option>
          <option value="light">{{ copy.settings.general.colorScheme.options.light }}</option>
          <option value="dark">{{ copy.settings.general.colorScheme.options.dark }}</option>
        </select>
      </div>
    </div>

    <h3>{{ copy.settings.general.conversationsTitle }}</h3>
    <div class="settings-card">
      <div class="settings-row settings-row--update">
        <div>
          <strong>{{ copy.settings.general.clearWebChats.title }}</strong>
          <span>{{ copy.settings.general.clearWebChats.description(webSessionCount) }}</span>
        </div>
        <div class="settings-row__actions">
          <button
            class="secondary-button secondary-button--danger"
            type="button"
            :disabled="webSessionCount === 0"
            @click="$emit('clear-web-sessions')"
          >
            {{ copy.settings.general.clearWebChats.action }}
          </button>
        </div>
      </div>
    </div>

    <h3>{{ copy.settings.general.update.title }}</h3>
    <p v-if="settingsState.updateNotice" class="settings-inline-status">{{ settingsState.updateNotice }}</p>
    <p v-if="settingsState.updateError" class="settings-inline-status settings-inline-status--error">
      {{ settingsState.updateError }}
    </p>
    <div class="settings-card">
      <div class="settings-row settings-row--update">
        <div>
          <strong>{{ updateStatusLabel }}</strong>
        </div>
        <div class="settings-row__actions">
          <button
            class="secondary-button"
            type="button"
            :disabled="settingsState.updateLoading"
            @click="$emit('check-update')"
          >
            {{ copy.settings.general.update.check }}
          </button>
          <button
            class="secondary-button"
            type="button"
            :disabled="settingsState.updateLoading || !settingsState.updateStatus.supported || settingsState.updateStatus.dirty"
            @click="$emit('run-update')"
          >
            {{ copy.settings.general.update.apply }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  copy: {
    type: Object,
    required: true,
  },
  form: {
    type: Object,
    required: true,
  },
  settingsState: {
    type: Object,
    required: true,
  },
  webSessionCount: {
    type: Number,
    required: true,
  },
  connectionState: {
    type: String,
    required: true,
  },
});

defineEmits([
  "save-connection-settings",
  "toggle-connection",
  "clear-web-sessions",
  "check-update",
  "run-update",
]);

const connectionSwitchChecked = computed(
  () => props.connectionState === "connected" || props.connectionState === "connecting",
);

const connectionSwitchLabel = computed(() => {
  if (props.connectionState === "connecting") {
    return props.copy.settings.general.gateway.connecting;
  }
  if (props.connectionState === "connected") {
    return props.copy.settings.general.gateway.connected;
  }
  return props.copy.settings.general.gateway.disconnected;
});

const updateStatusLabel = computed(() => {
  const status = props.settingsState.updateStatus || {};
  if (props.settingsState.updateLoading) {
    return props.copy.settings.general.update.checking;
  }
  if (!status.supported) {
    return props.copy.settings.general.update.unsupported;
  }
  if (status.dirty) {
    return props.copy.settings.general.update.dirty;
  }
  if (status.update_available) {
    return props.copy.settings.general.update.available(status.commits_behind || 0);
  }
  return props.copy.settings.general.update.current;
});
</script>
