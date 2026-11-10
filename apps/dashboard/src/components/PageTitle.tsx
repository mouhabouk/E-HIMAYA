import type { ReactNode, Ref } from "react";
import { IconTile, type IconName, type Tone } from "./Icon";
import { PrintButton } from "./PrintButton";

/**
 * Page heading of the design system (docs/design-system.md §3, UI-2): the section's icon tile, the same one as in
 * the navigation, next to the bold title. The tile is decorative; the heading text carries the meaning. `print`
 * adds the print button of the pages read on paper (a file, a guide, a list handed to a team).
 */
export function PageTitle({
  icon,
  tone,
  id,
  dir,
  ref,
  tabIndex,
  print,
  children,
}: {
  icon: IconName;
  tone: Tone;
  id?: string;
  dir?: "auto";
  ref?: Ref<HTMLHeadingElement>;
  tabIndex?: number;
  print?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="page-title">
      <IconTile name={icon} tone={tone} />
      <h1 id={id} dir={dir} ref={ref} tabIndex={tabIndex}>
        {children}
      </h1>
      {print && <PrintButton />}
    </div>
  );
}
