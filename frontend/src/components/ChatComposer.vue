<template>
  <form class="composer" @submit="$emit('submit', $event)">
    <label class="sr-only" for="messageInput">{{ copy.composer.label }}</label>
    <div v-if="commandHints.length" class="composer__commands" :aria-label="copy.composer.commandSuggestions">
      <button
        v-for="command in commandHints"
        :key="command.name"
        type="button"
        class="composer__command"
        @click="$emit('apply-command-hint', command)"
      >
        <code>{{ command.usage }}</code>
        <span>{{ command.description }}</span>
      </button>
    </div>
    <div class="composer__box">
      <textarea
        id="messageInput"
        :ref="setInputRef"
        :value="modelValue"
        rows="1"
        :placeholder="copy.composer.placeholder"
        :readonly="readOnly"
        autocomplete="off"
        @input="handleInput"
        @keydown="$emit('keydown', $event)"
      ></textarea>
      <button class="send-button" type="submit" :aria-label="copy.composer.sendAria" :disabled="disabled">
        {{ copy.composer.send }}
      </button>
    </div>
    <div class="composer__footer">
      <span>{{ copy.composer.disclaimer }}</span>
      <span>{{ runtimeHint }}</span>
    </div>
  </form>
</template>

<script setup>
defineProps({
  copy: {
    type: Object,
    required: true,
  },
  modelValue: {
    type: String,
    required: true,
  },
  disabled: {
    type: Boolean,
    required: true,
  },
  readOnly: {
    type: Boolean,
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
  setInputRef: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:modelValue", "input", "keydown", "submit", "apply-command-hint"]);

function handleInput(event) {
  emit("update:modelValue", event.target.value);
  emit("input", event);
}
</script>
