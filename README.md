# Day 06 · Data Ingestion Engineering — bài làm cá nhân

Pipeline biến 2 chương sách *Principles of Data Science* (OpenStax, CC BY-NC-SA 4.0) thành kho tri thức truy xuất được, rồi so sánh 3 chiến lược chuẩn bị dữ liệu trên cùng corpus, model và bộ 20 câu hỏi.

Đề bài gốc: [GUIDE.md](GUIDE.md), [BENCHMARK.md](BENCHMARK.md), [RUBRIC.md](RUBRIC.md), [SUBMISSION.md](SUBMISSION.md). Thông tin học viên: [STUDENT.md](STUDENT.md).

## Tóm tắt thiết kế

| Thành phần | Lựa chọn |
|---|---|
| Corpus | Chương 2 (PDF trang 67–103) và chương 8 (PDF trang 387–413), tổng **64 trang nội dung** — xem [starter/data/manifest.json](starter/data/manifest.json) |
| Đọc / chuẩn hóa | `pypdf` theo từng trang; bỏ header/footer lặp lại của OpenStax; Unicode NFKC, dấu nháy cong → ASCII; gộp khoảng trắng nhưng **giữ xuống dòng** |
| Metadata mỗi chunk | `document_id`, `source`, `page` (trang PDF), `chapter` (lọc), `section`, `section_title` |
| Embedding | OpenAI `text-embedding-3-small`, 1536 chiều, cùng model cho query và document |
| Vector store | Chroma `PersistentClient` (thư mục `starter/chroma_db`), metric cosine, HNSW (approximate). Dùng thay pgvector vì máy không có Docker — GUIDE cho phép |
| A | Cửa sổ cố định 500 ký tự, overlap 50, không lọc |
| B | Cắt tại heading mục (X.Y) + gom câu đến tối đa 1000 ký tự, không cắt giữa câu, không lọc |
| C | Giống hệt B (dùng chung index) + lọc `chapter` khi câu hỏi có filter — **chỉ khác B ở filter** |
| Benchmark | [benchmark/questions.json](benchmark/questions.json): 20 câu, 15 dev / 5 test, 3 câu có filter (1 ở test), evidence đã kiểm chứng tự động trong văn bản chuẩn hóa |

Tiêu chí chọn chiến lược, chốt **trước khi xem test**: dev Evidence Hit@3 cao nhất → hòa thì dev Hit@1 → hòa tiếp thì chiến lược đơn giản hơn.

## Cách chạy (Windows PowerShell)

```powershell
# 1. Môi trường (một lần)
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r starter/requirements.txt

# 2. Khai báo key (không commit file .env)
cd starter
Copy-Item .env.example .env
#   sửa .env:  OPENAI_API_KEY=sk-...   EMBEDDING_MODEL=text-embedding-3-small

# 3. Chạy toàn bộ pipeline
python -m src.run
```

Chạy lại lệnh ở bước 3 không tạo chunk trùng: chunk có ID ổn định, chunk nào nội dung không đổi thì không embed lại, chunk không còn tồn tại thì bị xóa. Pipeline tự kiểm tra điều này sau mỗi lần nạp và dừng nếu sai. Nếu API lỗi (sai key, hết quota), chương trình dừng và báo lỗi — không có vector giả.

## Kết quả được lưu ở đâu

| File | Nội dung |
|---|---|
| `starter/results/traces.jsonl` | Mỗi dòng = 1 câu × 1 chiến lược: top-3 chunk (ID, text, score, metadata), nhãn hit tự động |
| `starter/results/summary.json` | Hit@1, Evidence Hit@3 (n/N) theo chiến lược × dev/test, tỷ lệ tuân thủ filter |
| `starter/results/run_info.json` | Model, số chiều, phiên bản thư viện, tokens, chi phí, thời gian |
| `starter/results/ingest_log.json` | Số chunk, phân bố độ dài, thời gian ingest, kiểm tra nạp lại |
| `starter/results/corpus_report.json` | Trang rỗng, số dòng header/footer đã bỏ, số ký tự, danh sách mục |
| `starter/results/audit/*.csv` | Bảng chấm thủ công: coherence (10 vị trí × 3), metadata và grounding (5 câu test × 3) |
| `artifacts/experiment_log.csv` | Cấu hình, giả thuyết và kết quả A/B/C |
| `report/individual/` | Báo cáo cá nhân |

## Cấu trúc mã

```
starter/src/
  ingestion.py   đọc PDF, bỏ header/footer, chuẩn hóa, gắn chapter/section theo manifest
  chunking.py    fixed_size (A) và by_paragraph (B/C: theo mục + câu)
  embeddings.py  OpenAI embeddings, đếm token, không fallback
  store.py       Chroma: upsert theo ID, xóa chunk lỗi thời, search có filter
  evaluation.py  Hit@1 / Evidence Hit@3, trace, tổng hợp n/N
  run.py         nối các bước, lưu kết quả và mẫu bảng audit
```

`docker-compose.yml`, `init.sql`, `scripts/check_setup.py` thuộc starter pgvector gốc, không dùng trong bài này.

## Sử dụng AI

Mã nguồn, bộ câu hỏi và bản nháp báo cáo được viết với hỗ trợ của Claude (Anthropic). Học viên tự viết hàm `load_pdf` và chạy pipeline trên máy mình. Chi tiết cách kiểm tra ghi trong báo cáo cá nhân.
