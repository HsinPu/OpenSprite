<template>
  <div v-if="toasts.length" class="toast-stack" role="status" aria-live="polite">
    <article v-for="toast in toasts" :key="toast.id" class="toast" :data-tone="toast.tone || 'info'">
      <span>{{ toast.text }}</span>
      <button type="button" :aria-label="copy.settings.closeAria" @click="$emit('dismiss-toast', toast.id)">
        {{ copy.settings.close }}
      </button>
    </article>
  </div>
</template>

<script setup>
defineProps({
  copy: {
    type: Object,
    required: true,
  },
  toasts: {
    type: Array,
    required: true,
  },
});

defineEmits(["dismiss-toast"]);
</script>
