"""Day 06 pipeline: ingest → chunk → embed → store → retrieve → evaluate.

Chạy từ thư mục starter/:   python -m src.run
"""
import csv
import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_corpus
from .store import ChromaVectorStore, text_hash

ROOT = Path(__file__).resolve().parent.parent          # starter/
REPO = ROOT.parent
MANIFEST = ROOT / "data" / "manifest.json"
BENCHMARK = REPO / "benchmark" / "questions.json"
RESULTS = ROOT / "results"
CHROMA_PATH = ROOT / "chroma_db"
TOP_K = 3
PRICE_PER_1M_TOKENS = 0.02     # USD, text-embedding-3-small (giá niêm yết OpenAI)

# Ba cấu hình. B và C dùng CHUNG index (cùng chunk, cùng vector); khác biệt duy
# nhất là C áp filter metadata khi câu hỏi có filter.
STRATEGIES = {
    "A": {"chunking": "fixed_size", "chunk_size": 500, "overlap": 50, "index": "A",
          "use_filter": False,
          "hypothesis": "Baseline: cửa sổ cố định dễ cắt giữa câu/evidence, Hit@3 thấp hơn B."},
    "B": {"chunking": "by_section_sentence", "chunk_size": 1000, "overlap": 0, "index": "B",
          "use_filter": False,
          "hypothesis": "Cắt theo heading + ranh giới câu giữ trọn evidence nên Hit@3 và coherence cao hơn A."},
    "C": {"chunking": "by_section_sentence", "chunk_size": 1000, "overlap": 0, "index": "B",
          "use_filter": True,
          "hypothesis": "Giống B + lọc chapter khi câu hỏi có filter: loại chunk sai chương, tăng Hit cho câu filter."},
}
SELECTION_RULE = ("Chốt trước khi xem test: ưu tiên dev Evidence Hit@3 cao nhất; hòa thì "
                  "dev Hit@1; hòa tiếp thì chiến lược đơn giản/ít chunk hơn.")


def build_chunks(pages, index: str):
    if index == "A":
        cfg = STRATEGIES["A"]
        return [c for p in pages for c in fixed_size(p, cfg["chunk_size"], cfg["overlap"])]
    return [c for p in pages for c in by_paragraph(p, STRATEGIES["B"]["chunk_size"])]


def length_stats(chunks):
    lens = [len(c.text) for c in chunks]
    return {"chunks": len(lens), "min_chars": min(lens), "median_chars": statistics.median(lens),
            "mean_chars": round(statistics.mean(lens), 1), "max_chars": max(lens),
            "total_chars": sum(lens)}


def ingest(store: ChromaVectorStore, embedder: MyEmbedder, index: str, chunks) -> dict:
    """Upsert chỉ những chunk mới/đổi nội dung; xóa chunk cũ không còn tồn tại."""
    t0 = time.perf_counter()
    tokens_before = embedder.total_tokens
    existing = store.existing_hashes(index)
    todo = [c for c in chunks if existing.get(c.chunk_id) != text_hash(c.text)]
    if todo:
        vectors = embedder.embed_documents([c.text for c in todo])
        store.upsert(index, todo, vectors)
    removed = []
    for doc_id in sorted({c.document_id for c in chunks}):
        keep = {c.chunk_id for c in chunks if c.document_id == doc_id}
        removed += store.delete_obsolete(index, doc_id, keep)
    return {"embedded_chunks": len(todo), "skipped_unchanged": len(chunks) - len(todo),
            "removed_obsolete": len(removed), "store_count": store.count(index),
            "seconds": round(time.perf_counter() - t0, 2),
            "tokens": embedder.total_tokens - tokens_before}


def write_audit_templates(traces, pages, chunks_by_index):
    audit = RESULTS / "audit"
    audit.mkdir(parents=True, exist_ok=True)

    # 1) Coherence: 10 vị trí cố định chọn TRƯỚC khi xem điểm = điểm giữa văn bản
    #    của 10 trang được tính đầu tiên (sắp theo source_id, page).
    sample_pages = sorted(pages, key=lambda p: (p.document_id, p.page))[:10]
    rows = []
    for p in sample_pages:
        mid = len(p.text) // 2
        anchor = p.text[mid:mid + 60].replace("\n", " ")
        for strategy, index in [("A", "A"), ("B", "B"), ("C", "B")]:
            hit = None
            for c in chunks_by_index[index]:
                if c.document_id != p.document_id or c.page != p.page:
                    continue
                if index == "A":
                    if c.metadata["char_start"] <= mid < c.metadata["char_end"]:
                        hit = c; break
                elif " ".join(anchor.split()[1:5]) in c.text:
                    hit = c; break
            rows.append({"position_id": f"{p.document_id}:p{p.page}:mid", "strategy": strategy,
                         "chunk_id": hit.chunk_id if hit else "", "anchor_text": anchor,
                         "chunk_text": hit.text if hit else "", "score_0_2": "", "reason": ""})
    _write_csv(audit / "coherence_labels.csv", rows)

    # 2) Metadata + 3) Grounding: 5 câu test × top-3 cho mỗi chiến lược.
    meta_rows, ground_rows = [], []
    for t in traces:
        if t["split"] != "test":
            continue
        for h in t["hits"]:
            m = h["metadata"]
            meta_rows.append({"strategy": t["strategy"], "question_id": t["question_id"],
                              "rank": h["rank"], "chunk_id": h["chunk_id"],
                              "document_id": m.get("document_id"), "source": m.get("source"),
                              "page": m.get("page"), "chapter": m.get("chapter"),
                              "section": m.get("section"), "filter": json.dumps(t["filter"]),
                              "metadata_complete_and_correct": "", "error_note": ""})
        ground_rows.append({"strategy": t["strategy"], "question_id": t["question_id"],
                            "question": t["question"], "expected_answer": "",
                            "top3_chunk_ids": " | ".join(h["chunk_id"] for h in t["hits"]),
                            "auto_evidence_hit_at_3": t["hit_at_3"],
                            "grounding_0_2": "", "reason": ""})
    _write_csv(audit / "metadata_labels.csv", meta_rows)
    _write_csv(audit / "grounding_labels.csv", ground_rows)


def _write_csv(path: Path, rows: list[dict]):
    if path.exists():
        # Không ghi đè bảng đã chấm tay; xóa file nếu muốn tạo lại mẫu trống.
        print(f"Giữ nguyên {path.name} (đã tồn tại, có thể chứa nhãn thủ công)")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    load_dotenv(ROOT / ".env")
    RESULTS.mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1) Corpus
    t0 = time.perf_counter()
    pages, corpus_report = load_corpus(MANIFEST)
    corpus_report["load_seconds"] = round(time.perf_counter() - t0, 2)
    if len(pages) < 30:
        raise RuntimeError(f"Chỉ có {len(pages)} trang nội dung, cần ≥30")
    questions = json.loads(BENCHMARK.read_text(encoding="utf-8"))["questions"]
    print(f"Corpus: {len(pages)} trang nội dung · Benchmark: {len(questions)} câu")

    # 2) Chunk
    chunks_by_index = {idx: build_chunks(pages, idx) for idx in ("A", "B")}

    # 3) Embed + store (lỗi API sẽ dừng chương trình — không fallback)
    embedder = MyEmbedder()
    store = ChromaVectorStore(str(CHROMA_PATH), embedder.dimensions, embedder.model_name)
    ingest_log = {}
    for idx, chunks in chunks_by_index.items():
        first = ingest(store, embedder, idx, chunks)
        second = ingest(store, embedder, idx, chunks)      # kiểm tra nạp lại
        if second["embedded_chunks"] or second["store_count"] != len(chunks):
            raise RuntimeError(f"Nạp lại index {idx} không idempotent: {second}")
        ingest_log[idx] = {"first_pass": first, "reload_check": second,
                           "length_stats": length_stats(chunks)}
        print(f"Index {idx}: {len(chunks)} chunk, embed {first['embedded_chunks']}, "
              f"nạp lại thêm 0, store={second['store_count']}")

    # 4) Truy xuất top-3 cho mọi câu, mọi chiến lược (embed câu hỏi một lần)
    q_tokens_before = embedder.total_tokens
    t0 = time.perf_counter()
    qvec = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    traces = []
    for name, cfg in STRATEGIES.items():
        for q in questions:
            flt = q.get("filter") if cfg["use_filter"] else None
            hits = store.search(cfg["index"], qvec[q["id"]], TOP_K, flt)
            trace = evaluate_query(q, hits)
            trace.update(strategy=name, applied_filter=flt)
            traces.append(trace)
    query_seconds = round(time.perf_counter() - t0, 2)

    # 5) Lưu kết quả
    summary = summarize(traces)
    with (RESULTS / "traces.jsonl").open("w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    total_tokens = embedder.total_tokens
    run_info = {
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "platform": platform.platform(),
        "libraries": {lib: version(lib) for lib in ("pypdf", "chromadb", "openai", "python-dotenv")},
        "embedding": {"provider": "OpenAI", "model": embedder.model_name,
                      "dimensions": embedder.dimensions,
                      "query_document_handling": "cùng model, không tiền tố, không chuẩn hóa thêm"},
        "vector_store": {"name": "Chroma PersistentClient", "path": "starter/chroma_db",
                         "collections": ["day06_A", "day06_B"], "metric": "cosine",
                         "search": "approximate (HNSW)"},
        "tokens": {"total": total_tokens, "queries": total_tokens - q_tokens_before},
        "estimated_cost_usd": round(total_tokens / 1e6 * PRICE_PER_1M_TOKENS, 6),
        "query_seconds_all_strategies": query_seconds,
        "strategies": STRATEGIES, "top_k": TOP_K, "selection_rule": SELECTION_RULE,
    }
    _dump(RESULTS / "summary.json", summary)
    _dump(RESULTS / "run_info.json", run_info)
    _dump(RESULTS / "ingest_log.json", ingest_log)
    _dump(RESULTS / "corpus_report.json", corpus_report)
    write_audit_templates(traces, pages, chunks_by_index)
    _write_experiment_log(summary, ingest_log)

    print("\nKết quả (n/N):")
    for name in STRATEGIES:
        for split in ("dev", "test"):
            s = summary[name][split]
            print(f"  {name} {split:4}: Hit@1 {s['hit_at_1']:>5}  Evidence Hit@3 "
                  f"{s['evidence_hit_at_3']:>5}  filter {s['filter_compliance']}")
    print(f"Tokens: {total_tokens} · chi phí ước tính ${run_info['estimated_cost_usd']}")
    print(f"Đã lưu vào {RESULTS}")


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_experiment_log(summary, ingest_log) -> None:
    path = REPO / "artifacts" / "experiment_log.csv"
    fields = ["strategy", "chunking", "chunk_size", "overlap", "metadata", "filter", "vectorizer",
              "hypothesis", "dev_hit1", "dev_hit3", "test_hit1", "test_hit3", "notes"]
    rows = []
    for name, cfg in STRATEGIES.items():
        s = summary[name]
        log = ingest_log[cfg["index"]]
        rows.append({
            "strategy": name, "chunking": cfg["chunking"], "chunk_size": cfg["chunk_size"],
            "overlap": cfg["overlap"],
            "metadata": "document_id,source,page,chapter,section,section_title",
            "filter": "chapter (khi câu hỏi có filter)" if cfg["use_filter"] else "none",
            "vectorizer": f"OpenAI {os.environ.get('EMBEDDING_MODEL', '')}",
            "hypothesis": cfg["hypothesis"],
            "dev_hit1": s["dev"]["hit_at_1"], "dev_hit3": s["dev"]["evidence_hit_at_3"],
            "test_hit1": s["test"]["hit_at_1"], "test_hit3": s["test"]["evidence_hit_at_3"],
            "notes": f"{log['length_stats']['chunks']} chunk, index {cfg['index']}",
        })
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
