import numpy as np
import pytest

from idp.storage.local import LocalStorage


def test_bytes_roundtrip(tmp_path):
    st = LocalStorage(tmp_path)
    key = st.put_bytes("doc_1", "raw/a.pdf", b"%PDF-1.7")
    assert key == "doc_1/raw/a.pdf"
    assert st.get_bytes(key) == b"%PDF-1.7"
    assert st.path(key).is_file()


def test_image_roundtrip_rgb_and_gray(tmp_path):
    st = LocalStorage(tmp_path)
    rgb = np.zeros((10, 20, 3), np.uint8)
    rgb[..., 0] = 255  # pure red in RGB order
    key = st.put_image("doc_1", "pages/1.png", rgb)
    back = st.get_image(key)
    assert back.shape == (10, 20, 3)
    assert back[0, 0].tolist() == [255, 0, 0]
    gray = np.full((5, 5), 128, np.uint8)
    assert st.get_image(st.put_image("doc_1", "pages/g.png", gray)).shape == (5, 5)


def test_rejects_path_traversal(tmp_path):
    st = LocalStorage(tmp_path / "root")
    with pytest.raises(ValueError):
        st.put_bytes("doc_1", "../../evil.txt", b"x")
    with pytest.raises(ValueError):
        st.path("../outside")


def test_text_and_delete(tmp_path):
    st = LocalStorage(tmp_path)
    key = st.put_text("doc_1", "doc.md", "# Tiêu đề")
    assert st.get_text(key) == "# Tiêu đề"
    st.delete_document("doc_1")
    assert not st.exists(key)
