<template>
  <section class="settings-page">
    <div class="settings-card">
      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.shortcuts.openSettings }}</strong>
          <span>{{ copy.settings.shortcuts.openSettingsDescription }}</span>
        </div>
        <div class="shortcut-keys"><kbd>Ctrl</kbd><kbd>,</kbd></div>
      </div>
      <div class="settings-row">
        <div>
          <strong>{{ copy.settings.shortcuts.sendMessage }}</strong>
          <span>{{ copy.settings.shortcuts.sendMessageDescription }}</span>
        </div>
        <div class="shortcut-keys"><kbd>Enter</kbd></div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  copy: {
    type: Object,
    required: true,
  },
});
</script>
