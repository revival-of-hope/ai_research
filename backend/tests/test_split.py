from app.infrastructure.ingest.split import split_text


def test_split_keeps_overlap_and_content():
    text = "a" * 1600 + "。" + "b" * 1600
    chunks = split_text(text, chunk_size=1800, overlap=100)
    assert len(chunks) == 2
    assert chunks[0].endswith("。")
    assert chunks[1].startswith(chunks[0][-100:])


def test_split_discards_blank_input():
    assert split_text("  \n\n") == []
