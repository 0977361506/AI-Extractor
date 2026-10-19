import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api";
import type { VlmSettings } from "../types";
import { SettingsPage } from "./SettingsPage";

const saved: VlmSettings = {
  enabled: false, base_url: "", api_key: "", api_key_set: false, headers: {}, verify_ssl: true, ca_bundle: "", proxy: "",
  model: "", temperature: 0, max_tokens: 2048, structured_output: "auto", detected_mode: null, timeout_s: 60,
  max_concurrency: 4, retries: 2, max_image_side: 1600, vlm_threshold: 0.85, ui_threshold: 0.8,
  always_types: ["handwritten_note"], max_calls_per_page: 20,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.spyOn(api, "getVlmSettings").mockResolvedValue(saved);
    vi.spyOn(api, "vlmTests").mockResolvedValue([]);
  });

  it("tests the unsaved form and shows every step with hints", async () => {
    const test = vi.spyOn(api, "testVlm").mockResolvedValue({
      ok: false,
      detected_mode: null,
      recommended_concurrency: 1,
      steps: [
        { name: "network", ok: true, latency_ms: 12, detail: "TLS 1.3", hint: "" },
        { name: "models", ok: false, latency_ms: 30, detail: "HTTP 401: denied", hint: "Sai hoặc thiếu API key" },
      ],
    });
    renderPage();
    const url = await screen.findByLabelText(/base url/i);
    fireEvent.change(url, { target: { value: "https://llm-gw.mb.local/v1" } });
    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "sk-new" } });
    fireEvent.click(screen.getByRole("button", { name: /kiểm tra kết nối/i }));
    await waitFor(() => expect(test).toHaveBeenCalled());
    expect(test.mock.calls[0][0]).toMatchObject({ base_url: "https://llm-gw.mb.local/v1", api_key: "sk-new" });
    expect(await screen.findByText("HTTP 401: denied")).toBeInTheDocument();
    expect(screen.getByText(/Sai hoặc thiếu API key/)).toBeInTheDocument();
  });

  it("saves settings including custom headers", async () => {
    const save = vi.spyOn(api, "saveVlmSettings").mockResolvedValue({ ...saved, base_url: "https://gw/v1" });
    renderPage();
    fireEvent.change(await screen.findByLabelText(/base url/i), { target: { value: "https://gw/v1" } });
    fireEvent.click(screen.getByRole("button", { name: /thêm header/i }));
    fireEvent.change(screen.getByPlaceholderText("Tên header"), { target: { value: "X-Client-Id" } });
    fireEvent.change(screen.getByPlaceholderText("Giá trị"), { target: { value: "idp" } });
    fireEvent.click(screen.getByRole("button", { name: /^lưu/i }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0][0]).toMatchObject({ base_url: "https://gw/v1", headers: { "X-Client-Id": "idp" } });
  });
});
