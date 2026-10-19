import { useTranslation } from "react-i18next";
import { CATEGORY_ICON_PATHS } from "../lib/categoryIcons";
import type { Category } from "../lib/types";

export function CategoryIcon({ category, size = 18 }: { category: Category; size?: number }) {
  return (
    <svg className="cat-icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={CATEGORY_ICON_PATHS[category]} fillRule="evenodd" fill="currentColor" />
    </svg>
  );
}

export function CategoryLabel({ category }: { category: Category }) {
  const { t } = useTranslation();
  return (
    <span className={`cat cat--${category}`}>
      <CategoryIcon category={category} />
      <span>{t(`category.${category}`)}</span>
    </span>
  );
}
