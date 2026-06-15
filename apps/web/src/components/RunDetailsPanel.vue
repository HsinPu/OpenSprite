<template>
  <RunSummaryCard
    v-if="showRunSummary && currentRun && (currentRun.summary || currentRun.summaryLoading || currentRun.summaryError)"
    :copy="copy"
    :run="currentRun"
    @inspect-file="selectedFileChange = $event"
    @cleanup-worktree="$emit('cleanup-worktree', $event)"
    @resume-follow-up="$emit('resume-follow-up', $event)"
  />

  <RunTimeline
    v-if="showRunTimeline && runSummary"
    :copy="copy"
    :summary="runSummary"
    :events="runTimeline"
  />

  <RunTraceViewer
    v-if="showRunTrace && currentRun"
    :copy="copy"
    :run="currentRun"
    @cancel-run="$emit('cancel-run', $event)"
    @inspect-file="selectedFileChange = $event"
  />

  <RunFileChangeDrawer
    v-if="currentRun && selectedFileChange"
    :copy="copy"
    :run="currentRun"
    :change="selectedFileChange"
    @close="selectedFileChange = null"
    @revert-file-change="forwardRevertFileChange"
  />
</template>

<script setup>
import { ref, watch } from "vue";

import RunFileChangeDrawer from "./RunFileChangeDrawer.vue";
import RunSummaryCard from "./RunSummaryCard.vue";
import RunTimeline from "./RunTimeline.vue";
import RunTraceViewer from "./RunTraceViewer.vue";

const props = defineProps({
  copy: {
    type: Object,
    required: true,
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
});

const emit = defineEmits([
  "cancel-run",
  "cleanup-worktree",
  "resume-follow-up",
  "revert-file-change",
]);

const selectedFileChange = ref(null);

watch(
  () => props.currentRun?.runId,
  () => {
    selectedFileChange.value = null;
  },
);

function forwardRevertFileChange(change) {
  emit("revert-file-change", props.currentRun, change);
}
</script>
