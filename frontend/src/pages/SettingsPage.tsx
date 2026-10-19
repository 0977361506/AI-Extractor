import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { ConnectionTestResult, VlmSettings } from "../types";

const STEP_VI: Record<string, string> = {
  network: "Mạng (DNS · TCP · TLS)",
  models: "Xác thực & danh sách model",
  chat: "Chat văn bản",
  vision: "Đọc ảnh tiếng Việt",
  structured: "Đầu ra JSON có cấu trúc",
  summary: "Tổng kết",
};

const ALL_TYPES = ["handwritten_note", "form_field", "signature", "stamp", "figure", "table", "choice_group"];

export function SettingsPage() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["vlm-settings"], queryFn: api.getVlmSettings });
  const history = useQuery({ queryKey: ["vlm-tests"], queryFn: api.vlmTests });
  const [form, setForm] = useState<VlmSettings | null>(null);
  const [headers, setHeaders] = useState<[string, string][]>([]);
  const [result, setResult] = useState<ConnectionTestResult | null>(null);
  const [busy, setBusy] = useState<"" | "test" | "save">("");
  const [message, setMessage] = useState("");
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    if (settings.data && !form) {
      setForm(settings.data);
      setHeaders(Object.entries(settings.data.headers ?? {}));
    }
  }, [settings.data, form]);

  if (!form) return <div className="card">Đang tải cài đặt…</div>;

  const set = <K extends keyof VlmSettings>(k: K, v: VlmSettings[K]) => setForm({ ...form, [k]: v });
  const payload = (): Partial<VlmSettings> => ({ ...form, headers: Object.fromEntries(headers.filter(([k]) => k.trim())) });

  const runTest = async () => {
    setBusy("test");
    setMessage("");
    try {
      const r = await api.testVlm(payload());
      setResult(r);
      if (r.detected_mode && form.structured_output === "auto") set("detected_mode", r.detected_mode);
      qc.invalidateQueries({ queryKey: ["vlm-tests"] });
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy("");
    }
  };

  const save = async () => {
    setBusy("save");
    try {
      const s = await api.saveVlmSettings(payload());
      setForm(s);
      setMessage("Đã lưu cài đặt.");
      qc.setQueryData(["vlm-settings"], s);
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy("");
    }
  };

  const loadModels = async () => {
    try {
      setModels(await api.vlmModels());
    } catch (e) {
      setMessage(`Không lấy được danh sách model (hãy lưu cài đặt trước): ${e}`);
    }
  };

  const num = (k: keyof VlmSettings, label: string, step = 1) => (
    <label className="field">
      <span>{label}</span>
      <input type="number" step={step} value={form[k] as number} onChange={(e) => set(k, Number(e.target.value) as never)} />
    </label>
  );

  return (
    <div className="settings">
      <section className="card">
        <h2>Kết nối LLM Gateway (VLM)</h2>
        <label className="switch">
          <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <span>Bật gọi VLM cho vùng khó</span>
        </label>
        <div className="grid2">
          <label className="field">
            <span>Base URL</span>
            <input value={form.base_url} placeholder="https://llm-gateway.mb.local/v1" onChange={(e) => set("base_url", e.target.value)} />
          </label>
          <label className="field">
            <span>API key {form.api_key_set ? "(đã lưu)" : ""}</span>
            <input type="password" autoComplete="off" value={form.api_key} placeholder="sk-…" onChange={(e) => set("api_key", e.target.value)} />
          </label>
          <label className="field">
            <span>Model</span>
            <input list="vlm-models" value={form.model} placeholder="qwen2.5-vl-7b-instruct" onChange={(e) => set("model", e.target.value)} />
            <datalist id="vlm-models">{models.map((m) => <option key={m} value={m} />)}</datalist>
          </label>
          <div className="field">
            <span>&nbsp;</span>
            <button type="button" className="ghost" onClick={loadModels}>Lấy danh sách model</button>
          </div>
        </div>

        <h3>Header tùy chỉnh</h3>
        {headers.map(([k, v], i) => (
          <div className="header-row" key={i}>
            <input placeholder="Tên header" value={k} onChange={(e) => setHeaders(headers.map((h, j) => (j === i ? [e.target.value, h[1]] : h)))} />
            <input placeholder="Giá trị" value={v} onChange={(e) => setHeaders(headers.map((h, j) => (j === i ? [h[0], e.target.value] : h)))} />
            <button type="button" className="ghost" aria-label="Xóa header" onClick={() => setHeaders(headers.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <button type="button" className="ghost" onClick={() => setHeaders([...headers, ["", ""]])}>+ Thêm header</button>

        <h3>TLS / Mạng</h3>
        <div className="grid2">
          <label className="switch">
            <input type="checkbox" checked={form.verify_ssl} onChange={(e) => set("verify_ssl", e.target.checked)} />
            <span>Kiểm tra chứng chỉ SSL</span>
          </label>
          <label className="field">
            <span>File CA nội bộ</span>
            <input value={form.ca_bundle} placeholder="C:\certs\mb-root-ca.pem" onChange={(e) => set("ca_bundle", e.target.value)} />
          </label>
          <label className="field">
            <span>Proxy</span>
            <input value={form.proxy} placeholder="http://proxy:8080" onChange={(e) => set("proxy", e.target.value)} />
          </label>
        </div>

        <h3>Đầu ra & hiệu năng</h3>
        <div className="grid3">
          <label className="field">
            <span>Chế độ JSON</span>
            <select value={form.structured_output} onChange={(e) => set("structured_output", e.target.value as VlmSettings["structured_output"])}>
              <option value="auto">Tự dò{form.detected_mode ? ` (đang dùng: ${form.detected_mode})` : ""}</option>
              <option value="json_schema">json_schema</option>
              <option value="guided_json">guided_json (vLLM)</option>
              <option value="prompt_only">Chỉ prompt + tự kiểm tra</option>
            </select>
          </label>
          {num("temperature", "Temperature", 0.1)}
          {num("max_tokens", "Max tokens")}
          {num("timeout_s", "Timeout (giây)")}
          {num("max_concurrency", "Request đồng thời")}
          {num("retries", "Số lần thử lại")}
          {num("max_image_side", "Cạnh ảnh tối đa (px)")}
        </div>

        <h3>Định tuyến</h3>
        <div className="grid3">
          {num("vlm_threshold", "Ngưỡng gửi VLM", 0.01)}
          {num("ui_threshold", "Ngưỡng tô vàng UI", 0.01)}
          {num("max_calls_per_page", "Tối đa lượt gọi/trang")}
        </div>
        <div className="chips">
          {ALL_TYPES.map((t) => (
            <label key={t} className="chip">
              <input
                type="checkbox"
                checked={form.always_types.includes(t)}
                onChange={(e) => set("always_types", e.target.checked ? [...form.always_types, t] : form.always_types.filter((x) => x !== t))}
              />
              {t}
            </label>
          ))}
        </div>

        <div className="actions">
          <button type="button" onClick={runTest} disabled={busy !== ""}>{busy === "test" ? "Đang kiểm tra…" : "Kiểm tra kết nối"}</button>
          <button type="button" className="primary" onClick={save} disabled={busy !== ""}>Lưu cài đặt</button>
          {message && <span className="msg">{message}</span>}
        </div>
      </section>

      {result && (
        <section className="card">
          <h2>Kết quả kiểm tra {result.ok ? "✅" : "❌"}</h2>
          <ol className="steps">
            {result.steps.map((s) => (
              <li key={s.name} className={s.ok ? "ok" : "fail"}>
                <div className="step-head">
                  <span className="mark">{s.ok ? "✅" : "❌"}</span>
                  <strong>{STEP_VI[s.name] ?? s.name}</strong>
                  <span className="lat">{s.latency_ms} ms</span>
                </div>
                <div className="detail">{s.detail}</div>
                {s.hint && <div className="hint">Gợi ý: {s.hint}</div>}
              </li>
            ))}
          </ol>
        </section>
      )}

      {!!history.data?.length && (
        <section className="card">
          <h3>Lịch sử kiểm tra</h3>
          <ul className="history">
            {history.data.map((h) => (
              <li key={h.id}>
                {h.result.ok ? "✅" : "❌"} {new Date(h.created_at * 1000).toLocaleString("vi-VN")} —{" "}
                {h.result.steps.filter((s) => !s.ok).map((s) => STEP_VI[s.name] ?? s.name).join(", ") || "tất cả đạt"}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
