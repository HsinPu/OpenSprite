export const AUTHENTICATION_REQUIRED_EVENT = "opensprite:authentication-required";
export const AUTHENTICATION_REFRESHED_EVENT = "opensprite:authentication-refreshed";

export function notifyAuthenticationRequired(): void {
  window.dispatchEvent(new Event(AUTHENTICATION_REQUIRED_EVENT));
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status === 401) notifyAuthenticationRequired();
  else window.dispatchEvent(new Event(AUTHENTICATION_REFRESHED_EVENT));
  return response;
}
