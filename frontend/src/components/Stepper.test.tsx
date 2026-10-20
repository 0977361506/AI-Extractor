import { fireEvent, render, screen } from "@testing-library/react";
import { Stepper } from "./Stepper";

const steps = [
  { id: "ingest", label: "Nhận file", status: "done" as const, ms: 40 },
  { id: "preprocess", label: "Làm sạch ảnh", status: "done" as const, ms: 1250 },
  { id: "layout", label: "Bố cục", status: "running" as const },
  { id: "tables", label: "Bảng", status: "failed" as const, error: "boom" },
  { id: "vlm", label: "AI chuyên sâu", status: "skipped" as const, reason: "Chưa bật" },
  { id: "assemble", label: "Hoàn tất", status: "pending" as const },
];

describe("Stepper", () => {
  it("shows every step with its status and duration, and marks the selected one", () => {
    render(<Stepper steps={steps} selected="layout" onSelect={() => {}} />);
    const items = screen.getAllByRole("button");
    expect(items.map((b) => b.getAttribute("data-status"))).toEqual(["done", "done", "running", "failed", "skipped", "pending"]);
    expect(screen.getByRole("button", { name: /Bố cục/ })).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("1,3 s")).toBeInTheDocument();
    expect(screen.getByText("40 ms")).toBeInTheDocument();
  });

  it("selecting a step reports it; pending steps cannot be opened", () => {
    const onSelect = vi.fn();
    render(<Stepper steps={steps} selected="layout" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Làm sạch ảnh/ }));
    expect(onSelect).toHaveBeenCalledWith("preprocess");
    expect(screen.getByRole("button", { name: /Hoàn tất/ })).toBeDisabled();
  });
});
