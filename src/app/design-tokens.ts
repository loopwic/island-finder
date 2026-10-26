import type { TokenValue } from "@astryxdesign/core/theme";

// Foundations from the Figma file 「汇合 ERP · 界面重做」
// (https://www.figma.com/design/Whm5XAxAopZfHUKOlgjx7b, page 00 基础, node 8:2).
// Every name is the Astryx token the Figma variable's code syntax points at;
// pairs are [Light, Dark]. Change values in Figma first, then copy them here.
export const figmaTokens: Record<string, TokenValue> = {
  "--color-background-body": ["#efeff0", "#09090a"],
  "--color-background-surface": ["#f9f9fa", "#121213"],
  "--color-background-card": ["#ffffff", "#1c1c1d"],
  "--color-background-popover": ["#ffffff", "#212122"],
  "--color-background-muted": ["#efeff0", "#1a1a1b"],
  "--color-background-inverted": ["#1b1b1b", "#ffffff"],
  "--color-overlay-hover": ["#00000008", "#ffffff12"],
  "--color-overlay-pressed": ["#0000000d", "#ffffff1a"],
  "--color-overlay": ["#00000080", "#000000cc"],
  "--color-text-primary": ["#1b1b1b", "#ffffff"],
  "--color-text-secondary": ["#5c5c5e", "#959597"],
  "--color-text-disabled": ["#9c9d9f", "#6b6f76"],
  "--color-on-accent": "#ffffff",
  "--color-icon-primary": ["#1b1b1b", "#e3e4e6"],
  "--color-icon-secondary": ["#5c5c5e", "#959597"],
  "--color-icon-disabled": ["#9c9d9f", "#6b6f76"],
  "--color-border": ["#e2e2e2", "#212224"],
  "--color-border-emphasized": ["#d3d3d3", "#2c2d2f"],
  "--color-accent": "#5e6ad2",
  "--color-accent-muted": ["#ececed", "#29292b"],
  "--focus-outline-color": ["#6d78d5", "#5e6ad2"],
  "--color-success": "#4cb782",
  "--color-warning": "#e2a50a",
  "--color-error": "#d9343f",
  "--color-icon-blue": "#2f80ed",
  "--color-shadow": "#000000",

  // Six type sizes: 11 / 12 / 13 / 15 / 19 / 24.
  "--font-size-xs": "11px",
  "--font-size-sm": "12px",
  "--font-size-base": "13px",
  "--font-size-lg": "15px",
  "--font-size-xl": "19px",
  "--font-size-2xl": "24px",
  "--text-body-size": "13px",
  "--text-body-leading": "20px",
  "--text-body-weight": "400",
  "--text-large-size": "15px",
  "--text-large-leading": "24px",
  "--text-label-size": "12px",
  "--text-label-leading": "16px",
  "--text-label-weight": "500",
  "--text-supporting-size": "12px",
  "--text-supporting-leading": "16px",
  "--text-code-size": "12px",
  "--text-code-leading": "16px",
  "--text-heading-1-size": "24px",
  "--text-heading-1-leading": "32px",
  "--text-heading-1-weight": "600",
  "--text-heading-2-size": "19px",
  "--text-heading-2-leading": "28px",
  "--text-heading-2-weight": "600",
  "--text-heading-3-size": "15px",
  "--text-heading-3-leading": "22px",
  "--text-heading-3-weight": "500",
  // Section titles (DetailSection): 13/20 Medium.
  "--text-heading-4-size": "13px",
  "--text-heading-4-leading": "20px",
  "--text-heading-4-weight": "500",
  "--text-heading-5-size": "13px",
  "--text-heading-5-leading": "20px",
  "--text-heading-5-weight": "500",
  "--text-heading-6-size": "12px",
  "--text-heading-6-leading": "16px",
  "--text-heading-6-weight": "500",

  "--radius-inner": "6px",
  "--radius-element": "8px",
  "--radius-container": "12px",
  "--radius-page": "20px",
  "--border-width": "0.5px",

  // Control heights 28 / 32 / 36; toolbars and headers use sm.
  "--size-element-sm": "28px",
  "--size-element-md": "32px",
  "--size-element-lg": "36px",

  // Focus ring: 1px, flush with the control (keyboard only).
  "--focus-outline-width": "1px",
  "--focus-outline-offset": "0",

  // Low: main panel, cards, solid buttons. Med: menus, popovers, tooltips.
  // High: command menu, dialogs. Dark mode keeps only the edge layer.
  // light-dark() takes colors only, so the mode switch sits inside each layer.
  "--shadow-low":
    "0 3px 6px -2px light-dark(#00000005, #00000000), 0 1px 1px 0 light-dark(#0000000a, #0000004d)",
  "--shadow-med":
    "0 6px 18px 0 #00000005, 0 3px 9px 0 #0000000a, 0 1px 1px 0 #0000000a",
  "--shadow-high":
    "0 9px 48px 0 #00000014, 0 6px 24px 0 #0000001a, 0 1px 1px 0 #0000000a",
};

// Figma variables with no Astryx token (color/control/*, color/border/*).
// Dark values Figma did not expose to this session come from the design
// team's Linear measurements (docs/team/design/linear-reference.md in
// huivo-erp) and are marked "measured" there; the rest follow border-emphasized.
const control = {
  ring: "light-dark(#00000017, #ffffff24)",
  accent: "light-dark(#6d78d5, #5e6ad2)",
  accentHover: "#5561c4",
  accentPressed: "#4c57b6",
  switchOff: "light-dark(#cdcdcd, #36373a)",
  switchKnob: "#fffeff",
  inputBorder: "light-dark(#d8d8d8, #36373a)",
  inputBorderHover: "light-dark(#c2c2c2, #45464a)",
  chipBorder: "light-dark(#d3d3d3, #2c2d2f)",
  dialogBorder: "light-dark(#e8e8e8, #2c2d2f)",
  elevated: "light-dark(#ffffff, #212122)",
};

const ringAndLowShadow = `0 0 0 0.5px ${control.ring}, var(--shadow-low)`;

function lightDark(name: string): string {
  const value = figmaTokens[name];
  return Array.isArray(value) ? `light-dark(${value[0]}, ${value[1]})` : value;
}

const bodyText = {
  "--color-text-primary": lightDark("--color-text-primary"),
  "--color-text-secondary": lightDark("--color-text-secondary"),
  color: "var(--color-text-primary)",
};

// Notice tones (Figma color/state/attention, status/error, label/gray,
// status/success); banners tint with these at 8% and rule at 25%.
const tone = {
  attention: "#f2994a",
  error: "#d9343f",
  neutral: "#95a2b3",
  success: "#4cb782",
};

// Component specs from the Figma library page 01 组件 (按钮, 输入, 选择, 徽标,
// 对话框, 导航) applied through Astryx's public component overrides.
export const figmaComponents = {
  // Buttons are pills: 28px with 12/500 and 10px insets, 32px with 13/500
  // and 12px insets; icon and label sit 6px apart.
  button: {
    base: {
      borderRadius: "var(--radius-full)",
      gap: "var(--spacing-1-5)",
    },
    // Icon-only buttons stay square: Astryx labels them with aria-label and
    // zeroes their padding, so only text buttons get the Figma insets.
    "size:sm": {
      fontSize: "var(--text-label-size)",
      fontWeight: "500",
      ":not([aria-label])": { paddingBlock: "0", paddingInline: "10px" },
    },
    "size:md": {
      fontSize: "var(--text-body-size)",
      fontWeight: "500",
      ":not([aria-label])": { paddingBlock: "0", paddingInline: "12px" },
    },
    // Astryx's elevation:none class clears box-shadow at the same weight as
    // a variant key, so shadows are set on the combined key.
    "variant:primary+elevation:none": { boxShadow: "var(--shadow-low)" },
    "variant:secondary+elevation:none": { boxShadow: ringAndLowShadow },
    "variant:destructive+elevation:none": { boxShadow: "var(--shadow-low)" },
    "variant:primary": {
      "--focus-outline-offset": "1px",
      ":hover": { backgroundImage: "none", backgroundColor: control.accentHover },
      ":active": { backgroundImage: "none", backgroundColor: control.accentPressed },
    },
    // White button: card fill, a 9% ring and the panel shadow; no border.
    "variant:secondary": {
      backgroundColor: "var(--color-background-card)",
    },
    "variant:ghost": {
      color: "var(--color-text-secondary)",
      ":hover": { color: "var(--color-text-primary)" },
    },
    "variant:destructive": {
      backgroundColor: "var(--color-error)",
      color: "#ffffff",
      "--focus-outline-offset": "1px",
    },
  },
  // Sidebar items: 28px, 13/500 secondary, 6px icon gap, padding 0 9 0 8.
  "side-nav-item": {
    base: {
      height: "var(--size-element-sm)",
      minHeight: "var(--size-element-sm)",
      paddingLeft: "8px",
      paddingRight: "9px",
      gap: "var(--spacing-1-5)",
      fontSize: "var(--text-body-size)",
      fontWeight: "500",
      color: "var(--color-text-secondary)",
    },
    selected: {
      backgroundColor: "var(--color-overlay-pressed)",
      color: "var(--color-text-primary)",
    },
  },
  // Switch: 30×20 track, 14px knob inset 3px.
  switch: {
    "size:md": {
      width: "30px",
      height: "20px",
      padding: "3px",
      backgroundColor: control.switchOff,
    },
    checked: {
      backgroundColor: control.accent,
      "--focus-outline-offset": "1px",
    },
  },
  "switch-thumb": {
    "size:md": {
      width: "14px",
      height: "14px",
      backgroundColor: control.switchKnob,
    },
    // Knob travels 30 − 14 − 2×3 = 10px.
    "checked+size:md": { transform: "translateX(10px)" },
  },
  // Inputs: 32px, padding 6/12, radius 8, card fill, 0.5px input border.
  "text-input": {
    base: {
      paddingInline: "12px",
      backgroundColor: "var(--color-background-card)",
      borderColor: control.inputBorder,
      ":hover": { borderColor: control.inputBorderHover },
    },
  },
  "number-input": {
    base: {
      paddingInline: "12px",
      backgroundColor: "var(--color-background-card)",
      borderColor: control.inputBorder,
      ":hover": { borderColor: control.inputBorderHover },
    },
  },
  selector: {
    base: {
      fontSize: "var(--text-body-size)",
      backgroundColor: "var(--color-background-card)",
      borderColor: control.inputBorder,
      ":hover": { borderColor: control.inputBorderHover },
    },
  },
  // Field labels are Body/Strong; descriptions stay Supporting.
  "field-label": {
    base: {
      fontSize: "var(--text-body-size)",
      lineHeight: "var(--text-body-leading)",
      fontWeight: "500",
      color: "var(--color-text-primary)",
    },
  },
  // Tags: 24px pills on the panel color with the chip hairline.
  token: {
    base: {
      height: "24px",
      borderRadius: "var(--radius-full)",
      paddingInline: "var(--spacing-2)",
      gap: "var(--spacing-1-5)",
      backgroundColor: "var(--color-background-surface)",
      boxShadow: `inset 0 0 0 0.5px ${control.chipBorder}`,
      color: "var(--color-text-secondary)",
      fontWeight: "400",
    },
  },
  dialog: {
    base: {
      borderRadius: "21px",
      backgroundColor: control.elevated,
      border: `0.5px solid ${control.dialogBorder}`,
    },
  },
  // Figma 反馈/提示条: an 8% tone wash, 16px inline and 12px block insets, a
  // 14px tone icon. The full-width form (container:section) only rules its
  // bottom edge; the card form is rounded 8 with a 25% tone hairline.
  banner: {
    // Action and icon sit on the title row, not the block's center.
    base: {
      paddingBlock: "12px",
      paddingInline: "var(--spacing-4)",
      gap: "10px",
      alignItems: "flex-start",
    },
    "container:section": {
      borderRadius: "0",
      boxShadow: "inset 0 -0.5px 0 var(--color-border)",
    },
    "container:card": { borderRadius: "var(--radius-element)" },
    // Astryx repaints the text tokens in the status color on each status
    // key; the design keeps body text colors, so they are restored there.
    "status:warning": { ...bodyText, backgroundColor: `${tone.attention}14` },
    "status:error": { ...bodyText, backgroundColor: `${tone.error}14` },
    "status:info": { ...bodyText, backgroundColor: `${tone.neutral}14` },
    "status:success": { ...bodyText, backgroundColor: `${tone.success}14` },
    "status:warning+container:card": {
      boxShadow: `inset 0 0 0 0.5px ${tone.attention}40`,
    },
    "status:error+container:card": {
      boxShadow: `inset 0 0 0 0.5px ${tone.error}40`,
    },
    "status:info+container:card": {
      boxShadow: `inset 0 0 0 0.5px ${tone.neutral}40`,
    },
    "status:success+container:card": {
      boxShadow: `inset 0 0 0 0.5px ${tone.success}40`,
    },
  },
  "banner-icon": {
    base: { width: "14px", height: "14px", fontSize: "14px", marginTop: "3px" },
    "status:warning": { color: tone.attention },
    "status:error": { color: tone.error },
    "status:info": { color: "var(--color-icon-secondary)" },
    "status:success": { color: tone.success },
  },
  "empty-state-title": {
    base: {
      fontSize: "var(--text-body-size)",
      lineHeight: "var(--text-body-leading)",
      fontWeight: "500",
    },
  },
};

// Figma substitutes Noto Sans SC only because it lacks PingFang; code uses
// PingFang with the Windows system face as fallback.
const sansFallbacks =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif';

export const figmaTypography = {
  body: { family: "PingFang SC", fallbacks: sansFallbacks },
  heading: { family: "PingFang SC", fallbacks: sansFallbacks },
  code: {
    family: "JetBrains Mono",
    fallbacks: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
  },
};
