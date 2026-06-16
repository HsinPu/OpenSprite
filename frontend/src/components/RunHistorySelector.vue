<template>
  <section v-if="runs.length > 1 || loading || error" class="run-history" aria-live="polite">
    <div class="run-history__title">
      <span>{{ copy.runHistory.title }}</span>
      <small v-if="loading">{{ copy.runHistory.loading }}</small>
      <small v-else-if="error">{{ copy.runHistory.unavailable }}</small>
    </div>

    <label v-if="runs.length" class="run-history__select">
      <span class="sr-only">{{ copy.runHistory.select }}</span>
      <select :value="currentRun?.runId || ''" @change="$emit('select-run', $event.target.value)">
        <option v-for="(run, index) in runs" :key="run.runId" :value="run.runId">
          {{ runOptionLabel(run, index) }}
        </option>
      </select>
    </label>
  </section>
</template>

<script setup>
const props = defineProps({
  copy: {
    type: Object,
    required: true,
  },
  runs: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  error: {
    type: String,
    default: "",
  },
  currentRun: {
    type: Object,
    default: null,
  },
});

defineEmits(["select-run"]);

function shortRunId(runId) {
  const normalized = String(runId || "run").replace(/^run[_-]?/, "");
  return normalized.length > 8 ? normalized.slice(0, 8) : normalized;
}

function runOptionLabel(run, index) {
  const statusLabel = props.copy.run.statusLabels[run.status] || run.status;
  const prefix = index === 0 ? props.copy.runHistory.latest : `#${index + 1}`;
  return `${prefix} · Run ${shortRunId(run.runId)} · ${statusLabel}`;
}
</script>
