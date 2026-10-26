export const settingsTabs = [
  { value: 'devices', label: '设备连接' },
  { value: 'recognition', label: '识别设置' },
  { value: 'firmware', label: '开发板固件' },
] as const;

export type SettingsTab = (typeof settingsTabs)[number]['value'];

export function parseSettingsTab(value: unknown): SettingsTab | undefined {
  return settingsTabs.some((tab) => tab.value === value) ? (value as SettingsTab) : undefined;
}
