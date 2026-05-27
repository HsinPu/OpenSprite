<template>
  <section v-if="requests.length || state.loading || state.error" class="permission-panel" aria-live="polite">
    <div class="permission-panel__header">
      <div>
        <span>{{ copy.permissions.eyebrow }}</span>
        <strong>{{ copy.permissions.title }}</strong>
      </div>
      <small v-if="state.loading">{{ copy.permissions.loading }}</small>
    </div>

    <p v-if="state.error" class="permission-panel__error">{{ state.error }}</p>

    <article v-for="request in requests" :key="request.requestId" class="permission-card">
      <div class="permission-card__body">
        <strong>{{ request.toolName }}</strong>
        <p>{{ request.reason || copy.permissions.noReason }}</p>
        <dl class="permission-card__meta">
          <div v-if="request.actionType">
            <dt>{{ copy.permissions.actionType }}</dt>
            <dd>{{ request.actionType }}</dd>
          </div>
          <div v-if="request.riskLevel || request.riskLevels?.length">
            <dt>{{ copy.permissions.riskLevel }}</dt>
            <dd>{{ formatRiskLevels(request) }}</dd>
          </div>
          <div v-if="request.resource">
            <dt>{{ copy.permissions.resource }}</dt>
            <dd>{{ request.resource }}</dd>
          </div>
          <div v-if="request.preview">
            <dt>{{ copy.permissions.preview }}</dt>
            <dd>{{ request.preview }}</dd>
          </div>
        </dl>
        <code>{{ request.requestId }}</code>
      </div>
      <div class="permission-card__actions">
        <button
          class="secondary-button"
          type="button"
          :disabled="Boolean(state.resolvingIds[request.requestId])"
          @click="$emit('resolve-permission', request, 'deny')"
        >
          {{ copy.permissions.deny }}
        </button>
        <button
          class="primary-button"
          type="button"
          :disabled="Boolean(state.resolvingIds[request.requestId])"
          @click="$emit('resolve-permission', request, 'approve')"
        >
          {{ state.resolvingIds[request.requestId] ? copy.permissions.resolving : copy.permissions.approve }}
        </button>
      </div>
    </article>
  </section>
</template>

<script setup>
defineProps({
  copy: {
    type: Object,
    required: true,
  },
  state: {
    type: Object,
    required: true,
  },
  requests: {
    type: Array,
    required: true,
  },
});

defineEmits(["resolve-permission"]);

function formatRiskLevels(request) {
  const risks = Array.isArray(request?.riskLevels)
    ? request.riskLevels.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  if (risks.length) {
    return risks.join(", ");
  }
  return String(request?.riskLevel || "").trim();
}
</script>
