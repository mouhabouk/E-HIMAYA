// covers: the damages of a mission record (Yamen, 2026-11-01): the burnt forest in hectares, the farm loss in hectares
// or bales, the places and crops from the reference lists.
import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { DamageEntry } from "../lib/missionRecord";
import { renderApp } from "../test/render";
import { DamagesEditor } from "./DamagesEditor";

function Harness({ onChange }: { onChange: (lines: DamageEntry[]) => void }) {
  const [lines, setLines] = useState<DamageEntry[]>([]);
  return (
    <DamagesEditor
      value={lines}
      onChange={(next) => {
        setLines(next);
        onChange(next);
      }}
    />
  );
}

describe("DamagesEditor", () => {
  it("records a forest in hectares and a fodder loss in bales", async () => {
    const onChange = vi.fn();
    renderApp(<Harness onChange={onChange} />, { lang: "fr" });
    fireEvent.click(screen.getByRole("button", { name: "Ajouter un dégât" }));
    expect(screen.getByLabelText("Unité")).toBeDisabled();
    await screen.findByRole("option", { name: "غابة" });
    fireEvent.change(screen.getByLabelText("Lieu"), { target: { value: "غابة" } });
    fireEvent.change(screen.getByLabelText("Quantité"), { target: { value: "2.5" } });
    expect(onChange).toHaveBeenLastCalledWith([{ kind: "forest", place: "غابة", crop: null, unit: "ha", value: 2.5 }]);

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un dégât" }));
    const kinds = screen.getAllByLabelText("Nature");
    fireEvent.change(kinds[1] as HTMLElement, { target: { value: "agri" } });
    fireEvent.change(screen.getAllByLabelText("Lieu")[1] as HTMLElement, { target: { value: "حقل" } });
    fireEvent.change(screen.getByLabelText("Culture"), { target: { value: "قرط" } });
    fireEvent.change(screen.getAllByLabelText("Quantité")[1] as HTMLElement, { target: { value: "40" } });
    expect(onChange).toHaveBeenLastCalledWith([
      { kind: "forest", place: "غابة", crop: null, unit: "ha", value: 2.5 },
      { kind: "agri", place: "حقل", crop: "قرط", unit: "bale", value: 40 },
    ]);
    fireEvent.click(screen.getByRole("button", { name: "Retirer la ligne 1" }));
    expect(onChange).toHaveBeenLastCalledWith([{ kind: "agri", place: "حقل", crop: "قرط", unit: "bale", value: 40 }]);
  });
});
