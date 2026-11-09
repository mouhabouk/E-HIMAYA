import { afterEach, describe, expect, it } from "vitest";
import { applyBrand, otherBrand, storedBrand } from "./brand";

describe("brand colour (design-system §2.0)", () => {
  afterEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.brand;
  });

  it("is royal blue by default", () => {
    expect(storedBrand()).toBe("blue");
    expect(document.documentElement.dataset.brand).toBeUndefined();
  });

  it("keeps royal red on the device and marks the page", () => {
    applyBrand("red");
    expect(storedBrand()).toBe("red");
    expect(document.documentElement.dataset.brand).toBe("red");
    applyBrand(otherBrand("red"));
    expect(storedBrand()).toBe("blue");
    expect(document.documentElement.dataset.brand).toBeUndefined();
  });
});
