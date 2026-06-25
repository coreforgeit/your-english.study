const rawDebug = import.meta.env.VITE_DEBUG ?? 'true';

export const DEBUG = rawDebug === true || rawDebug === 'true' || rawDebug === '1';

const stripTrailingSlash = (value: string): string => value.replace(/\/+$/, '');

const defaultBackendUrl = DEBUG ? 'http://localhost:8000' : 'https://api.your-english.study';
const defaultFrontendUrl = DEBUG ? 'http://localhost:5173' : 'https://app.your-english.study';

export const BACKEND_URL = stripTrailingSlash(import.meta.env.VITE_API_URL || defaultBackendUrl);
export const FRONTEND_URL = stripTrailingSlash(
  import.meta.env.VITE_FRONTEND_URL || defaultFrontendUrl,
);
