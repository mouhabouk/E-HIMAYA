import type { ReactNode, Ref } from "react";
import { IconTile, type IconName, type Tone } from "./Icon";

/**
 * Page heading of the design system (docs/design-system.md §3, UI-2): the section's icon tile, the same one as in
 * the navigation, next to the bold title. The tile is decorative; the heading text carries the meaning.
 */
export function PageTitle({
  icon,
  tone,
  id,
  dir,
  ref,
  tabIndex,
  children,
}: {
  icon: IconName;
  tone: Tone;
  id?: string;
  dir?: "auto";
  ref?: Ref<HTMLHeadingElement>;
  tabIndex?: number;
  children: ReactNode;
}) {
  return (
    <div className="page-title">
      <IconTile name={icon} tone={tone} />
      <h1 id={id} dir={dir} ref={ref} tabIndex={tabIndex}>
        {children}
      </h1>
    </div>
  );
}
