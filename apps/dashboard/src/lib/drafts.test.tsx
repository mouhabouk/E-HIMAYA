import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { pendingDrafts, useDraft } from "./drafts";

afterEach(() => {
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("useDraft (backlog G4)", () => {
  it("keeps the text when the form unmounts and restores it when it comes back", () => {
    const first = renderHook(() => useDraft("report:r1:note"));
    act(() => first.result.current[1]("équipe envoyée"));
    first.unmount();

    const again = renderHook(() => useDraft("report:r1:note"));
    expect(again.result.current[0]).toBe("équipe envoyée");
    // Another record has its own draft.
    expect(renderHook(() => useDraft("report:r2:note")).result.current[0]).toBe("");
  });

  it("drops the draft after clear (a successful send)", () => {
    const { result, unmount } = renderHook(() => useDraft("contact:c1:text"));
    act(() => result.current[1]("réponse"));
    act(() => result.current[2]());
    expect(result.current[0]).toBe("");
    unmount();
    expect(window.sessionStorage.getItem("ehimaya.draft.contact:c1:text")).toBeNull();
  });

  it("asks before leaving the tab only while a draft holds text", () => {
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const { result, unmount } = renderHook(() => useDraft("incident:i1:note"));
    expect(pendingDrafts()).toBe(0);

    act(() => result.current[1]("renfort demandé"));
    expect(pendingDrafts()).toBe(1);
    expect(add).toHaveBeenCalledWith("beforeunload", expect.any(Function));

    act(() => result.current[1]("   "));
    expect(pendingDrafts()).toBe(0);
    expect(remove).toHaveBeenCalledWith("beforeunload", expect.any(Function));
    unmount();
  });
});
