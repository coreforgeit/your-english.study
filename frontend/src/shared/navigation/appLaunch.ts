export const AppLaunchMode = {
  REPEAT: 'repeat',
} as const;

export type AppLaunchMode = (typeof AppLaunchMode)[keyof typeof AppLaunchMode];

export const AppLaunchQuery = {
  MODE: 'mode',
  AUTO_START: 'autoStart',
} as const;

export const APP_LAUNCH_AUTO_START_VALUE = 'true';

export function parseAppLaunchMode(value: unknown): AppLaunchMode | null {
  return value === AppLaunchMode.REPEAT ? AppLaunchMode.REPEAT : null;
}
