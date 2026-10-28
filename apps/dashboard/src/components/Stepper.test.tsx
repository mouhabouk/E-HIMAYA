import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { I18nextProvider } from "react-i18next";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createI18n } from "../i18n";
import { Stepper, type StepperProps } from "./Stepper";

function Harness(props: Omit<StepperProps, "value" | "onChange"> & { start: number | null; spy?: (n: number) => void }) {
  const { start, spy, ...rest } = props;
  const [value, setValue] = useState<number | null>(start);
  return (
    <>
      <label htmlFor="s">السعة</label>
      <Stepper
        id="s"
        {...rest}
        value={value}
        onChange={(n) => {
          spy?.(n);
          setValue(n);
        }}
        onClear={() => setValue(null)}
      />
    </>
  );
}

const show = (ui: React.ReactElement) => render(<I18nextProvider i18n={createI18n("ar")}>{ui}</I18nextProvider>);

describe("Stepper (R4a)", () => {
  afterEach(() => vi.useRealTimers());

  it("steps with the buttons, names them, and stops at the bounds", () => {
    show(<Harness start={1} min={0} max={2} label="السعة" />);
    const field = screen.getByLabelText("السعة", { selector: "input" });
    const plus = screen.getByRole("button", { name: "زيادة السعة" });
    const minus = screen.getByRole("button", { name: "إنقاص السعة" });
    fireEvent.pointerDown(plus, { button: 0 });
    fireEvent.pointerUp(plus);
    expect(field).toHaveValue(2);
    expect(plus).toBeDisabled();
    fireEvent.pointerDown(minus, { button: 0 });
    fireEvent.pointerUp(minus);
    fireEvent.pointerDown(minus, { button: 0 });
    fireEvent.pointerUp(minus);
    expect(field).toHaveValue(0);
    expect(minus).toBeDisabled();
  });

  it("steps from the keyboard once, not twice, and keeps the step grid", () => {
    const spy = vi.fn();
    show(<Harness start={500} min={0} max={20000} step={500} spy={spy} label="السعة" />);
    fireEvent.click(screen.getByRole("button", { name: "زيادة السعة" }), { detail: 0 });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenLastCalledWith(1000);
  });

  it("speeds up on a long press and stops on release", () => {
    vi.useFakeTimers();
    const spy = vi.fn();
    show(<Harness start={0} min={0} max={1000} spy={spy} />);
    const plus = screen.getByRole("button", { name: "زيادة" });
    fireEvent.pointerDown(plus, { button: 0 });
    act(() => {
      vi.advanceTimersByTime(400 + 80 * 12);
    });
    fireEvent.pointerUp(plus);
    const reached = spy.mock.lastCall?.[0] as number;
    // 1 on press, 10 single steps, then two steps of ten.
    expect(reached).toBe(31);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(spy.mock.lastCall?.[0]).toBe(reached);
  });

  it("stays typeable, caps the maximum and lifts a low value on blur", () => {
    const spy = vi.fn();
    show(<Harness start={5} min={5} max={50} spy={spy} />);
    const field = screen.getByLabelText("السعة", { selector: "input" });
    fireEvent.change(field, { target: { value: "1" } });
    expect(spy).toHaveBeenLastCalledWith(1);
    fireEvent.blur(field);
    expect(spy).toHaveBeenLastCalledWith(5);
    fireEvent.change(field, { target: { value: "900" } });
    expect(spy).toHaveBeenLastCalledWith(50);
    fireEvent.change(field, { target: { value: "" } });
    expect(field).toHaveValue(null);
  });
});
