<template>
  <main class="chat-panel">
    <header class="topbar">
      <div class="topbar__title">
        <strong>{{ copy.chat.title }}</strong>
        <span>{{ sessionMeta }}</span>
      </div>

      <div class="connection-card" aria-live="polite">
        <span class="status-dot" :class="statusDotClass"></span>
        <strong>{{ connectionLabel }}</strong>
        <button
          class="ghost-button"
          type="button"
          :disabled="connecting"
          @click="$emit('connect')"
        >
          {{ connectButtonLabel }}
        </button>
      </div>
    </header>

    <div
      v-show="notice.text"
      class="notice-banner"
      role="status"
      :data-tone="notice.tone || 'info'"
    >
      {{ notice.text }}
    </div>

    <section class="chat-workspace">
      <section :ref="setMessageStageRef" class="message-stage" aria-live="polite">
        <div class="conversation-wrap">
          <EmptyState
            v-if="entries.length === 0 && messages.length === 0"
            :copy="copy"
            :prompts="prompts"
            @apply-prompt="$emit('apply-prompt', $event)"
          />

          <MessageList :copy="copy" :entries="entries" :messages="messages" :display-name="displayName" />

          <WorkStateCard
            v-if="showWorkState && workState"
            :copy="copy"
            :work-state="workState"
            @resume-follow-up="$emit('resume-follow-up', $event)"
            @run-verification="$emit('run-verification', $event)"
          />

          <PermissionPanel
            :copy="copy"
            :state="permissionState"
            :requests="permissionRequests"
            @resolve-permission="forwardPermissionResolution"
          />
        </div>
      </section>

      <aside class="trace-inspector" aria-label="Run trace inspector">
        <RunDetailsPanel
          :copy="copy"
          :runs="runs"
          :runs-loading="runsLoading"
          :runs-error="runsError"
          :current-run="currentRun"
          :run-timeline="runTimeline"
          :run-summary="runSummary"
          :show-run-history="showRunHistory"
          :show-run-timeline="showRunTimeline"
          :show-run-summary="showRunSummary"
          :show-run-trace="showRunTrace"
          @select-run="$emit('select-run', $event)"
          @cancel-run="$emit('cancel-run', $event)"
          @cleanup-worktree="$emit('cleanup-worktree', $event)"
          @resume-follow-up="$emit('resume-follow-up', $event)"
          @revert-file-change="forwardRunFileRevert"
        />
      </aside>
    </section>

    <ChatComposer
      :copy="copy"
      :model-value="messageText"
      :set-input-ref="setMessageInputRef"
      :disabled="sendDisabled"
      :read-only="composerReadOnly"
      :runtime-hint="runtimeHint"
      :command-hints="commandHints"
      @update:model-value="$emit('update-message-text', $event)"
      @input="$emit('composer-input')"
      @keydown="$emit('composer-keydown', $event)"
      @submit="$emit('submit-message', $event)"
      @apply-command-hint="$emit('apply-command-hint', $event)"
    />

  </main>
</template>

<script setup>
import ChatComposer from "./ChatComposer.vue";
import EmptyState from "./EmptyState.vue";
import MessageList from "./MessageList.vue";
import PermissionPanel from "./PermissionPanel.vue";
import RunDetailsPanel from "./RunDetailsPanel.vue";
import WorkStateCard from "./WorkStateCard.vue";

const props = defineProps({
  copy: {
    type: Object,
    required: true,
  },
  prompts: {
    type: Array,
    required: true,
  },
  entries: {
    type: Array,
    required: true,
  },
  messages: {
    type: Array,
    required: true,
  },
  workState: {
    type: Object,
    default: null,
  },
  runs: {
    type: Array,
    required: true,
  },
  runsLoading: {
    type: Boolean,
    required: true,
  },
  runsError: {
    type: String,
    default: "",
  },
  currentRun: {
    type: Object,
    default: null,
  },
  runTimeline: {
    type: Array,
    required: true,
  },
  runSummary: {
    type: Object,
    default: null,
  },
  permissionState: {
    type: Object,
    required: true,
  },
  permissionRequests: {
    type: Array,
    required: true,
  },
  showWorkState: {
    type: Boolean,
    required: true,
  },
  showRunHistory: {
    type: Boolean,
    required: true,
  },
  showRunTimeline: {
    type: Boolean,
    required: true,
  },
  showRunSummary: {
    type: Boolean,
    required: true,
  },
  showRunTrace: {
    type: Boolean,
    required: true,
  },
  notice: {
    type: Object,
    required: true,
  },
  sessionMeta: {
    type: String,
    required: true,
  },
  runtimeHint: {
    type: String,
    required: true,
  },
  commandHints: {
    type: Array,
    default: () => [],
  },
  displayName: {
    type: String,
    required: true,
  },
  messageText: {
    type: String,
    required: true,
  },
  connectionLabel: {
    type: String,
    required: true,
  },
  connectButtonLabel: {
    type: String,
    required: true,
  },
  statusDotClass: {
    type: Object,
    required: true,
  },
  sendDisabled: {
    type: Boolean,
    required: true,
  },
  composerReadOnly: {
    type: Boolean,
    required: true,
  },
  connecting: {
    type: Boolean,
    required: true,
  },
  setMessageInputRef: {
    type: Function,
    required: true,
  },
  setMessageStageRef: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits([
  "connect",
  "apply-prompt",
  "update-message-text",
  "composer-input",
  "composer-keydown",
  "submit-message",
  "apply-command-hint",
  "cancel-run",
  "resolve-permission",
  "revert-file-change",
  "cleanup-worktree",
  "resume-follow-up",
  "run-verification",
  "select-run",
]);

function forwardPermissionResolution(request, decision) {
  emit("resolve-permission", request, decision);
}

function forwardRunFileRevert(run, change) {
  emit("revert-file-change", run, change);
}
</script>
