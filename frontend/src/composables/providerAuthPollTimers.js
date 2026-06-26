export function createProviderAuthPollTimers() {
  const providerAuthPollTimers = new Map();

  function clearProviderAuthPollTimer(providerId) {
    const timer = providerAuthPollTimers.get(providerId);
    if (timer) {
      clearTimeout(timer);
      providerAuthPollTimers.delete(providerId);
    }
  }

  function scheduleProviderAuthPoll(providerId, auth, poll) {
    clearProviderAuthPollTimer(providerId);
    const delayMs = Math.max(3, auth.pollIntervalSeconds || 5) * 1000;
    providerAuthPollTimers.set(providerId, window.setTimeout(() => {
      void poll();
    }, delayMs));
  }

  function clearProviderAuthPollTimers(providerIds) {
    for (const providerId of providerIds) {
      clearProviderAuthPollTimer(providerId);
    }
  }

  return {
    clearProviderAuthPollTimer,
    scheduleProviderAuthPoll,
    clearProviderAuthPollTimers,
  };
}
