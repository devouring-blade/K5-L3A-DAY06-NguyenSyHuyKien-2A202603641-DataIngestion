"""Evaluate retrieved evidence and preserve per-query traces."""
import re
from collections import defaultdict
from typing import Any


def _ws(text: str) -> str:
    """So khớp không phân biệt khoảng trắng/xuống dòng và hoa/thường.

    Cần vì chunk B nối các dòng bằng dấu cách, còn evidence chép từ trang có
    xuống dòng — nội dung giống nhau, chỉ khác khoảng trắng.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def _token_overlap(evidence: str, text: str) -> float:
    ev = re.findall(r"\w+", evidence.lower())
    if not ev:
        return 0.0
    words = set(re.findall(r"\w+", text.lower()))
    return round(sum(w in words for w in ev) / len(ev), 3)


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page and FULL gold evidence; keep hit@1 and hit@3 trace.

    Một hit = chunk thuộc đúng nguồn + trang gold VÀ chứa đủ evidence_quote.
    Không suy ra nhãn coherence/grounding từ so khớp chuỗi — các nhãn đó chấm tay.
    """
    gold_pages = set(question["gold_page"])
    evidence = _ws(question["evidence_quote"])
    flt = question.get("filter") or {}
    judged = []
    for h in hits:
        m = h["metadata"]
        source_ok = m.get("document_id") == question["gold_source_id"] and m.get("page") in gold_pages
        evidence_ok = evidence in _ws(h["text"])
        judged.append({
            **h,
            "source_page_match": source_ok,
            "evidence_full": evidence_ok,
            "evidence_token_overlap": _token_overlap(question["evidence_quote"], h["text"]),
            "is_hit": source_ok and evidence_ok,
            "respects_filter": all(m.get(k) == v for k, v in flt.items()) if flt else None,
        })
    # Evidence bị tách qua nhiều chunk: đúng trang, có một phần evidence nhưng không chunk nào đủ.
    split_evidence = (not any(j["is_hit"] for j in judged)
                      and any(j["source_page_match"] and j["evidence_token_overlap"] >= 0.3 for j in judged))
    return {
        "question_id": question["id"],
        "split": question["split"],
        "type": question.get("type"),
        "question": question["question"],
        "filter": question.get("filter"),
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "hit_at_1": bool(judged) and judged[0]["is_hit"],
        "hit_at_3": any(j["is_hit"] for j in judged[:3]),
        "gold_page_in_top3": any(j["source_page_match"] for j in judged[:3]),
        "possible_split_evidence": split_evidence,
        "filter_respected_top3": (all(j["respects_filter"] for j in judged[:3]) if flt else None),
        "hits": judged,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split (n/N)."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in traces:
        groups[(t["strategy"], t["split"])].append(t)
        groups[(t["strategy"], "all")].append(t)
    out: dict[str, Any] = {}
    for (strategy, split), ts in sorted(groups.items()):
        n = len(ts)
        h1 = sum(t["hit_at_1"] for t in ts)
        h3 = sum(t["hit_at_3"] for t in ts)
        with_filter = [t for t in ts if t["filter"]]
        respected = sum(bool(t["filter_respected_top3"]) for t in with_filter)
        out.setdefault(strategy, {})[split] = {
            "N": n,
            "hit_at_1": f"{h1}/{n}", "hit_at_1_rate": round(h1 / n, 3) if n else None,
            "evidence_hit_at_3": f"{h3}/{n}", "evidence_hit_at_3_rate": round(h3 / n, 3) if n else None,
            "gold_page_in_top3": f"{sum(t['gold_page_in_top3'] for t in ts)}/{n}",
            "possible_split_evidence": [t["question_id"] for t in ts if t["possible_split_evidence"]],
            "filter_compliance": (f"{respected}/{len(with_filter)}" if with_filter else "N/A"),
        }
    return out
