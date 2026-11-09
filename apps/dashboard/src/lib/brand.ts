/**
 * Brand colour (docs/design-system.md §2.0, Yamen 2026-11-08): white stays the base colour; the user picks royal blue
 * (default) or royal red for the frame around the screen and the primary colour. Kept on this device only and applied
 * before the first paint by index.html.
 */
export const BRANDS = ["blue", "red"] as const;
export type Brand = (typeof BRANDS)[number];
const STORAGE_KEY = "ehimaya.brand";

export function storedBrand(): Brand {
  try {
    return localStorage.getItem(STORAGE_KEY) === "red" ? "red" : "blue";
  } catch {
    return "blue";
  }
}

export function applyBrand(brand: Brand, doc: Document = document): void {
  if (brand === "red") doc.documentElement.dataset.brand = "red";
  else delete doc.documentElement.dataset.brand;
  try {
    if (brand === "red") localStorage.setItem(STORAGE_KEY, "red");
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private window: the choice lasts for this page only */
  }
}

export function otherBrand(brand: Brand): Brand {
  return brand === "red" ? "blue" : "red";
}
