"""Compare predicted ASTs against ground-truth ASTs (``<dir>/<doc>/ast.json``) → per-page CER / TEDS report."""

from __future__ import annotations

import statistics
from pathlib import Path

from idp.assemble.render_text import element_markdown
from idp.core.ast import Document, ElementType, Page
from idp.evaluation.metrics import cer, teds
from idp.table.render import cells_to_html


def page_text(page: Page) -> str:
    parts = []
    for el in sorted(page.elements, key=lambda e: e.reading_order):
        if el.type == ElementType.TABLE:
            parts.append(" ".join(c.text for c in sorted(el.cells, key=lambda c: (c.row, c.col))))
        else:
            parts.append(el.text or element_markdown(el))
    return "\n".join(p for p in parts if p)


def _tables(page: Page) -> list[str]:
    return [cells_to_html(e.cells) for e in sorted(page.elements, key=lambda e: e.reading_order) if e.type == ElementType.TABLE and e.cells]


def evaluate_documents(gt_dir: Path, pred_dir: Path) -> dict:
    docs = []
    for gt_file in sorted(Path(gt_dir).glob("*/ast.json")):
        name = gt_file.parent.name
        pred_file = Path(pred_dir) / name / "ast.json"
        if not pred_file.exists():
            docs.append({"name": name, "error": "missing prediction"})
            continue
        gt = Document.model_validate_json(gt_file.read_text(encoding="utf-8"))
        pred = Document.model_validate_json(pred_file.read_text(encoding="utf-8"))
        pred_pages = {p.page_number: p for p in pred.pages}
        pages = []
        for gp in gt.pages:
            pp = pred_pages.get(gp.page_number)
            if pp is None:
                pages.append({"page": gp.page_number, "cer": 1.0, "teds": 0.0 if _tables(gp) else None})
                continue
            gt_tables, pred_tables = _tables(gp), _tables(pp)
            table_scores = [teds(pred_tables[i] if i < len(pred_tables) else "", ref) for i, ref in enumerate(gt_tables)]
            pages.append(
                {
                    "page": gp.page_number,
                    "cer": round(cer(page_text(pp), page_text(gp)), 4),
                    "teds": round(statistics.fmean(table_scores), 4) if table_scores else None,
                }
            )
        docs.append({"name": name, "pages": pages})
    all_pages = [p for d in docs for p in d.get("pages", [])]
    teds_vals = [p["teds"] for p in all_pages if p["teds"] is not None]
    summary = {
        "documents": len(docs),
        "pages": len(all_pages),
        "mean_cer": round(statistics.fmean(p["cer"] for p in all_pages), 4) if all_pages else None,
        "mean_teds": round(statistics.fmean(teds_vals), 4) if teds_vals else None,
    }
    return {"summary": summary, "documents": docs}
