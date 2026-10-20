import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api";
import type { DocumentRow } from "../types";
import { DocumentListPage } from "./DocumentListPage";

class SilentES {
  addEventListener() {}
  close() {}
}

const row = (id: string, filename: string, extra: Partial<DocumentRow> = {}): DocumentRow => ({
  document_id: id, job_id: "j", filename, status: "COMPLETED", total_pages: 1, done_pages: 1, created_at: 0, ...extra,
});

function renderPage(rows: DocumentRow[]) {
  vi.stubGlobal("EventSource", SilentES);
  vi.spyOn(api, "listDocuments").mockResolvedValue(rows);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <DocumentListPage onOpen={() => {}} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("DocumentListPage", () => {
  it("dropped files join the queue and the first one opens in the step view", async () => {
    renderPage([row("doc_old", "cu.pdf")]);
    vi.spyOn(api, "upload").mockResolvedValue({
      documents: [
        { document_id: "doc_a", filename: "a.pdf", status: "PENDING" },
        { document_id: "doc_b", filename: "b.xlsx", status: "PENDING" },
        { filename: "x.exe", error: "Định dạng không được hỗ trợ" },
      ],
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.pdf"), new File(["y"], "b.xlsx")] } });
    const queue = await screen.findByRole("list", { name: "Hàng chờ" });
    expect(within(queue).getAllByRole("button").map((b) => b.textContent)).toEqual([expect.stringContaining("a.pdf"), expect.stringContaining("b.xlsx")]);
    expect(within(queue).getByRole("button", { name: /a\.pdf/ })).toHaveAttribute("aria-pressed", "true");
    expect(document.querySelector(".process .fname")?.textContent).toBe("a.pdf");
    fireEvent.click(within(queue).getByRole("button", { name: /b\.xlsx/ }));
    expect(document.querySelector(".process .fname")?.textContent).toBe("b.xlsx");
    expect(screen.getByText(/x\.exe: Định dạng không được hỗ trợ/)).toBeInTheDocument();
  });

  it("any listed document can be opened in the step view", async () => {
    renderPage([row("doc_old", "cu.pdf")]);
    fireEvent.click(await screen.findByRole("button", { name: "Quy trình" }));
    await waitFor(() => expect(document.querySelector(".process .fname")?.textContent).toBe("cu.pdf"));
  });
});
