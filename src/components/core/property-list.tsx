import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { AppIcon, type AppIconName } from "./icons";
import { propertyStyles } from "./property-list.stylex";

export function PropertyList({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <dl {...stylex.props(propertyStyles.list)} aria-label={label}>
      {children}
    </dl>
  );
}

/** One property: label column, then a value led by its semantic icon. */
export function PropertyRow({
  label,
  icon,
  isControl = false,
  children,
}: {
  label: string;
  icon?: AppIconName;
  isControl?: boolean;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(propertyStyles.row)}>
      <dt {...stylex.props(propertyStyles.label)}>{label}</dt>
      <dd
        {...stylex.props(
          propertyStyles.value,
          isControl && propertyStyles.controlValue,
        )}
      >
        {icon && !isControl && <PropertyIcon name={icon} />}
        {children}
      </dd>
    </div>
  );
}

function PropertyIcon({ name }: { name: AppIconName }) {
  return (
    <span {...stylex.props(propertyStyles.icon)} aria-hidden>
      <AppIcon name={name} />
    </span>
  );
}

/** An editable property value that opens its editor. */
export function PropertyControl({
  label,
  icon,
  onClick,
  children,
}: {
  label: string;
  icon?: AppIconName;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      {...stylex.props(propertyStyles.control)}
    >
      {icon && <PropertyIcon name={icon} />}
      <span {...stylex.props(propertyStyles.controlText)}>{children}</span>
    </button>
  );
}
