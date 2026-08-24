import { Linking } from 'react-native';

const CALLBACK_MARKER = 'upstox-oauth';

export function isUpstoxCallback(url) {
  return typeof url === 'string' && url.includes(CALLBACK_MARKER);
}

export function parseUpstoxCallback(url) {
  if (!isUpstoxCallback(url)) return null;
  try {
    const parsed = new URL(url);
    return {
      code: parsed.searchParams.get('code'),
      state: parsed.searchParams.get('state'),
      error: parsed.searchParams.get('error'),
      errorDescription: parsed.searchParams.get('error_description'),
    };
  } catch {
    return null;
  }
}

export function subscribeToUpstoxRedirect(handler) {
  const listener = ({url}) => handler(parseUpstoxCallback(url));
  const subscription = Linking.addEventListener('url', listener);
  Linking.getInitialURL().then(url => {
    if (url) handler(parseUpstoxCallback(url));
  });
  return () => subscription.remove();
}
