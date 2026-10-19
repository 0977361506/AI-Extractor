import { useEffect, useState } from "react";
import { DocumentListPage } from "./pages/DocumentListPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VerifyPage } from "./pages/VerifyPage";

type Route = { name: "list" } | { name: "doc"; id: string } | { name: "settings" };

function parse(hash: string): Route {
  const [, a, b] = hash.replace(/^#/, "").split("/");
  if (a === "doc" && b) return { name: "doc", id: b };
  if (a === "settings") return { name: "settings" };
  return { name: "list" };
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (hash: string) => {
    window.location.hash = hash;
  };

  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="brand" onClick={() => go("/")}>
          <span className="logo">IDP</span> Đối chiếu hồ sơ
        </button>
        <nav>
          <button type="button" className={route.name === "list" ? "active" : ""} onClick={() => go("/")}>Hồ sơ</button>
          <button type="button" className={route.name === "settings" ? "active" : ""} onClick={() => go("/settings")}>Cài đặt VLM</button>
        </nav>
      </header>
      <main>
        {route.name === "list" && <DocumentListPage onOpen={(id) => go(`/doc/${id}`)} />}
        {route.name === "doc" && <VerifyPage key={route.id} documentId={route.id} />}
        {route.name === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}
