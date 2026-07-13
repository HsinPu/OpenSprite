export interface ProviderAuthPollState {
  pollIntervalSeconds?: number;
}

export function createProviderAuthPollTimers() {
  const providerAuthPollTimers = new Map<string, number>();

  function clearProviderAuthPollTimer(providerId: string): void {
    const timer = providerAuthPollTimers.get(providerId);
    if (timer) {
      clearTimeout(timer);
      providerAuthPollTimers.delete(providerId);
    }
  }

  function scheduleProviderAuthPoll(providerId: string, auth: ProviderAuthPollState, poll: () => void | Promise<void>): void {
    clearProviderAuthPollTimer(providerId);
    const delayMs = Math.max(3, auth.pollIntervalSeconds || 5) * 1000;
    providerAuthPollTimers.set(providerId, window.setTimeout(() => {
      void poll();
    }, delayMs));
  }

  function clearProviderAuthPollTimers(providerIds: string[]): void {
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
