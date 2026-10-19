from idp.jobs.db import Database


def test_schema_and_kv(tmp_path):
    db = Database(tmp_path / "idp.sqlite")
    db.set_setting("vlm", {"a": 1})
    assert db.get_setting("vlm") == {"a": 1}
    assert db.get_setting("missing", {"x": 2}) == {"x": 2}


def test_documents_events_and_corrections(tmp_path):
    db = Database(tmp_path / "idp.sqlite")
    db.create_document("doc_1", "job_1", "a.pdf", total_pages=3)
    db.update_document("doc_1", status="IN_PROGRESS", done_pages=1)
    doc = db.get_document("doc_1")
    assert doc["status"] == "IN_PROGRESS" and doc["done_pages"] == 1 and doc["filename"] == "a.pdf"
    assert [d["document_id"] for d in db.list_documents()] == ["doc_1"]
    e1 = db.add_event("doc_1", {"progress_percentage": 10})
    e2 = db.add_event("doc_1", {"progress_percentage": 20})
    assert [e["progress_percentage"] for e in db.events_after("doc_1", 0)] == [10, 20]
    assert [e["progress_percentage"] for e in db.events_after("doc_1", e1)] == [20]
    assert e2 > e1
    cid = db.add_correction("doc_1", "el_p1_002", "cells[3][2].text", "15.250.0O0", "15.250.000", "rm.local")
    rows = db.list_corrections("doc_1")
    assert rows[0]["id"] == cid and rows[0]["new_value"] == "15.250.000"
    db.delete_document("doc_1")
    assert db.get_document("doc_1") is None


def test_cache(tmp_path):
    db = Database(tmp_path / "idp.sqlite")
    assert db.cache_get("k") is None
    db.cache_put("k", {"text": "x"})
    assert db.cache_get("k") == {"text": "x"}


def test_connection_test_history(tmp_path):
    db = Database(tmp_path / "idp.sqlite")
    db.add_connection_test({"ok": True, "steps": []})
    db.add_connection_test({"ok": False, "steps": []})
    hist = db.list_connection_tests()
    assert [h["result"]["ok"] for h in hist] == [False, True]
