# Báo cáo cá nhân — Day 6

**Học viên:** Nguyễn Sỹ Huy Kiên · **MSSV:** 2A202603641 · **Lớp:** L3A · **Ngày chạy:** 2026-11-13 (UTC 15:51)

> **Về cách làm bài.** Mã nguồn, bộ câu hỏi, bản nháp nhãn chấm tay và bản nháp báo cáo này được soạn với hỗ trợ của Claude (Anthropic). Học viên tự viết hàm `load_pdf`, tự xác định ranh giới trang và chạy pipeline trên máy mình. Mọi con số trong báo cáo lấy từ lần chạy thật trong `starter/results/`. Nhãn coherence và grounding là nhãn **AI soạn nháp, học viên duyệt lại**; nhãn metadata được kiểm tra bằng script đối chiếu với trang nguồn rồi đọc lại. Không dùng LLM để chấm tự động trong pipeline.

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang, quy tắc tính trang.** Sách *Principles of Data Science* (OpenStax, ©2025 Rice University, giấy phép CC BY-NC-SA 4.0; dùng phi thương mại cho mục đích học tập, có ghi nguồn). Chọn 2 chương có chung chủ đề "thu thập dữ liệu" nhưng khác góc nhìn, để filter theo chương có tác dụng thật: Chương 2 *Collecting and Preparing Data* (trang PDF 67–103, 37 trang) và Chương 8 *Ethics Throughout the Data Science Cycle* (trang PDF 387–413, 27 trang). **Tổng 64 trang nội dung.** Quy tắc tính: từ trang mở chương đến trang ngay trước mục "Key Terms"; loại Key Terms, Group Project, Chapter Review, Critical Thinking, Quantitative Problems, References. Số trang là số trang vật lý của PDF (bắt đầu từ 1); trang in = trang PDF − 10. Ranh giới được kiểm tra bằng cách đọc chữ của từng trang biên. Lần kiểm tra này phát hiện và sửa một lỗi: trang 421 thuộc chương 9, không thuộc chương 8. Chi tiết trong [manifest](../../starter/data/manifest.json).
- **Chuẩn hóa, lỗi và giới hạn.** `pypdf` trích chữ từng trang. **Không có trang rỗng** trong 64 trang. Bỏ 97 dòng header/footer lặp lại (56 ở chương 2, 41 ở chương 8): dạng "58 2 • Collecting and Preparing Data", "Access for free at openstax.org", "2.1 • Overview ... 59", và chữ trang trí ở trang mở chương. Chuẩn hóa Unicode NFKC, đổi dấu nháy cong và gạch dài sang ASCII, gộp khoảng trắng trong mỗi dòng nhưng **giữ xuống dòng** để nhận diện heading. Sau chuẩn hóa còn 110 828 ký tự (chương 2) và 83 266 ký tự (chương 8). Giới hạn: (1) bảng bị trích thành văn bản phẳng, mất cấu trúc hàng/cột (ví dụ Table 2.1, 2.2); (2) PDF không giữ dòng trống, nên không khôi phục được ranh giới đoạn; (3) câu bị ngắt dòng giữa chừng được giữ nguyên trong trang (B nối lại khi tách câu). Không cần OCR.
- **Embedding, vector store, lệnh chạy, chi phí.** OpenAI `text-embedding-3-small`, 1536 chiều (thư viện `openai` 3.50.0). Query và document dùng cùng model, không tiền tố. Vector store là **Chroma 1.5.9** `PersistentClient` tại `starter/chroma_db`, metric cosine, HNSW (tìm kiếm xấp xỉ), mỗi index một collection (`day06_A`, `day06_B`). Dùng Chroma thay pgvector vì máy không có Docker (GUIDE cho phép). Lệnh chạy: `cd starter; python -m src.run`. Môi trường: Python 3.13.14, Windows 11, pypdf 7.0.1. Tổng **79 172 token**, chi phí ước tính **$0.0016** theo giá niêm yết $0.02/1M token. Thời gian đọc PDF và chuẩn hóa là 13,96 giây.
- **Metadata.** Bắt buộc: `document_id` (pds-ch02 / pds-ch08), `source` (đường dẫn PDF), `page` (trang PDF). Bổ sung: `chapter` (int, **trường lọc**), `section` và `section_title` (vd "2.4 Data Cleaning and Preprocessing"). Giá trị `chapter` lấy từ manifest. Danh sách mục lấy từ chính footer của sách (dòng "2.1 • Overview of Data Collection Methods"), không tự đặt. `section` được gán bằng cách dò dòng heading "X.Y Tên mục" khớp đúng danh sách đó. Lý do chọn `chapter`: hai chương cùng bàn về thu thập, kiểm định, thiên lệch dữ liệu, nên câu hỏi dễ lấy nhầm chương; người dùng thường biết mình đang học chương nào trước khi hỏi.

## Cấu hình và benchmark

- **A / B / C.**
  - **A:** `fixed_size`, cửa sổ 500 ký tự, overlap 50, theo từng trang; `section` = mục hiệu lực ở đầu trang. Không lọc.
  - **B:** `by_paragraph`, cắt tại heading cấp mục X.Y, trong mỗi mục gom câu liền nhau đến tối đa 1000 ký tự, không bao giờ cắt giữa câu, theo từng trang. Không lọc.
  - **C:** **dùng chung index với B** (cùng chunk, cùng vector) và lọc `chapter` trong Chroma (`where`) **chỉ khi câu hỏi có filter**; câu không có filter chạy y như B. Vì vậy **khác biệt duy nhất giữa B và C là filter**; A và B khác nhau ở cách chunk.
  - Cả ba dùng cùng corpus, model, store, metric và top-3.
- **Benchmark.** [benchmark/questions.json](../../benchmark/questions.json): 20 câu tiếng Anh (cùng ngôn ngữ với sách), **15 dev / 5 test**, chia tay trước khi chạy truy xuất. Loại câu: trực tiếp, diễn đạt lại, điều kiện. Có **3 câu có filter**: q13 (chương 8) và q14 (chương 2) ở dev, **q17 (chương 8) ở test**. Mỗi câu có `expected_answer`, `gold_source_id`, `gold_page`, `evidence_quote`. Evidence được **kiểm tra tự động** là chuỗi con nguyên văn (sau khi gộp khoảng trắng) của trang gold đã chuẩn hóa, và mỗi evidence chỉ xuất hiện ở đúng một trang. Filter là ngữ cảnh người dùng giả định cung cấp trước ("đang học chương Ethics"), không suy từ đáp án. Nguy cơ rò rỉ: q20 (test) và q04 (dev) cùng ở trang 74; cùng một người viết cả dev lẫn test.
- **Tiêu chí chọn, chốt trước khi xem test:** dev Evidence Hit@3 cao nhất → hòa thì dev Hit@1 → hòa tiếp thì chiến lược đơn giản hơn / ít chunk hơn.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí ingest |
|---|---|---|---|---|---|---|
| A | dev | 8/15 | 10/15 | 455 | 5,80 s | 42 644 token ≈ $0.00085 |
| A | test | 3/5 | 3/5 | 455 | | |
| B | dev | 11/15 | **15/15** | 242 | 2,57 s | 36 241 token ≈ $0.00072 |
| B | test | 3/5 | 4/5 | 242 | | |
| C | dev | 11/15 | **15/15** | 242 (dùng chung B) | 0 (dùng index B) | 0 |
| C | test | 3/5 | 4/5 | 242 | | |

Embed 20 câu hỏi tốn 287 token. Truy xuất 60 lượt (20 câu × 3 chiến lược) mất 3,96 giây. Chạy lại pipeline lần thứ hai không embed thêm chunk nào, số bản ghi giữ nguyên 455 / 242 (`reload_check` trong `ingest_log.json`).

Độ dài chunk: A trung vị 500 ký tự (từ 70 đến 500, tổng 213 644 ký tự do overlap); B trung vị 903,5 ký tự (từ 17 đến 1039, tổng 193 916 ký tự).

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ, test (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,80 (n=10) | 10/15 | 0/1 | 0 / 1 / 4 → 1,80 |
| B | 1,50 (n=10) | 15/15 | 0/1 (không áp filter) | 0 / 1 / 4 → 1,80 |
| C | 1,50 (n=10, chung chunk B) | 15/15 | **1/1** | 0 / 1 / 4 → 1,80 |

Tuân thủ filter trên toàn bộ 3 câu có filter (dev + test): A 1/3, B 0/3, C **3/3**.

**Đường dẫn và cách chọn mẫu.**
- Trace đầy đủ: `starter/results/traces.jsonl`. Tổng hợp: `summary.json`. Cấu hình và môi trường: `run_info.json`.
- Nhãn tay nằm trong `starter/results/audit/`:
  - **Coherence:** 10 vị trí chọn trước khi xem điểm = điểm giữa văn bản của 10 trang được tính đầu tiên, sắp theo (source_id, page). Đó là các trang 67–76, đều thuộc chương 2.
  - **Metadata:** 5 câu test × top-3 × 3 chiến lược.
  - **Grounding:** 5 câu test × 3 chiến lược.

## Phân tích và kết luận

- **A–B (chỉ đổi cách chunk).**
  - B tăng Evidence Hit@3 dev từ 10/15 lên 15/15 và Hit@1 dev từ 8/15 lên 11/15, với ít hơn một nửa số chunk (242 so với 455) và ít token hơn.
  - Nguyên nhân chính: cửa sổ cố định **cắt evidence làm đôi**. Với A, evidence của q02, q04, q15, q20 **không nằm trọn trong bất kỳ chunk nào** của trang gold, nên A không thể hit dù truy xuất đúng trang (A lấy được trang gold trong top-3 ở 20/20 câu).
  - Coherence tăng từ 0,80 lên 1,50.
  - Metadata của A sai `section` ở 5/15 bản ghi test: A gán mục ở đầu trang cho cả trang, nên chunk sau heading "8.3" ở trang 405 bị ghi "8.2". B cắt tại heading nên đúng 15/15.
  - Trên test, khác biệt nhỏ hơn (Evidence Hit@3 3/5 so với 4/5).
- **B–C (chỉ đổi filter).**
  - Trên dev, Hit không đổi (15/15, 11/15): hai câu filter q13, q14 B vốn đã trả đúng chunk ở hạng 1. Nhưng top-3 của B vẫn lẫn chunk chương khác (tuân thủ filter 0/2), còn C 2/2.
  - Trên test, q17 ("What is data validation?", ngữ cảnh chương 8): B trả **cả 3 chunk từ chương 2 trang 94**, nơi cũng bàn về data validation. C lọc về đúng chương 8 trang 403 (`gold_page_in_top3` B 4/5 → C 5/5) nhưng vẫn **không hit**. Lý do: chunk chứa định nghĩa (`B:pds-ch08:p403:1`) ghép chung với ví dụ che dữ liệu "Luke Smith ... LS97" ở đầu, nên embedding bị loãng và chunk này xếp sau các chunk khác cùng trang.
  - Filter sửa được lỗi **sai phạm vi** nhưng không sửa được lỗi **xếp hạng trong phạm vi đúng**.
- **Hai ví dụ sai.**
  1. **q02, chiến lược A** (pds-ch02, trang 73): định nghĩa cluster sampling dài khoảng 230 ký tự bị cửa sổ 500/50 cắt ngang. Chunk hạng 1 chỉ chứa 81% token của evidence, nên A miss cả Hit@1 lẫn Hit@3. B lấy trọn câu ở hạng 1.
  2. **q17, chiến lược B và C** (gold pds-ch08, trang 403): như phân tích ở trên. B sai chương, C đúng chương nhưng không lấy được chunk định nghĩa. Lưu ý: cờ `possible_split_evidence` mà evaluation gán cho q17/C là **báo động giả** của heuristic. Kiểm tra tay cho thấy evidence nằm trọn trong `B:pds-ch08:p403:1`, chỉ là chunk này không vào top-3.

  Thêm một trường hợp đáng ghi: **q20/A** bị tính trượt tự động vì chunk hạng 1 bắt đầu bằng "e results of quota sampling..." (cửa sổ cắt mất "th"). Người chấm xác nhận đây là **bằng chứng tương đương** và chấm grounding = 2, nhưng **không** sửa chỉ số Hit theo định nghĩa chính.
- **Chiến lược chọn: B**, theo đúng quy tắc đã chốt. B và C hòa ở dev Evidence Hit@3 (15/15) và dev Hit@1 (11/15), nên quy tắc phụ "đơn giản hơn" chọn B. Kết quả test (B = C = 4/5 Hit@3) được xem sau và không làm đổi lựa chọn.
  - **Nhìn lại:** quy tắc chọn đã không tính tới tỷ lệ tuân thủ filter, trong khi C hơn B rõ rệt ở chỉ số này (3/3 so với 0/3) mà không tốn thêm chi phí (dùng chung index). Nếu triển khai thật cho người dùng có ngữ cảnh chương, **C là lựa chọn phù hợp hơn**. Lần sau nên đưa tuân thủ filter vào tiêu chí chọn ngay từ đầu.
  - **Đánh đổi:** B và C có chunk dài hơn (khoảng 900 ký tự) nên đưa nhiều ngữ cảnh hơn vào top-3, nhưng chunk ghép nhiều ý dễ bị loãng như q17. A dễ cài đặt, không phụ thuộc cấu trúc sách, nhưng làm vỡ evidence và gán sai mục.
  - **Điều kiện áp dụng:** kết quả chỉ đúng cho corpus PDF có heading đánh số rõ ràng như sách OpenStax. Không suy rộng sang tài liệu khác.
- **Hạn chế.**
  - Test chỉ có 5 câu và chỉ 1 câu filter: một câu đổi kết quả là thay đổi 20 điểm phần trăm.
  - Nhãn coherence/grounding do **AI soạn nháp và học viên duyệt**, một người chấm, có thể thiên lệch vì người chấm biết chiến lược của từng chunk.
  - Mẫu coherence chỉ gồm trang chương 2.
  - Evidence ngắn (một câu) thuận lợi cho chunk dài hơn.
  - Một trang test trùng trang với dev (trang 74).
  - Thời gian chỉ đo một lần trên laptop. Chi phí ước tính từ số token và giá niêm yết, không lấy từ hóa đơn.
  - Bảng bị dàn phẳng. Chunk không vượt ranh giới trang, nên mảnh đầu trang như "business success." (17 ký tự) trở thành chunk riêng thiếu ngữ cảnh.
- **Nếu làm lại hoặc mở rộng.**
  - Tách thêm theo tiêu đề nhỏ trong mục (như "Data Validation", "Sampling") và theo khối EXAMPLE, để chunk định nghĩa không bị ghép với ví dụ (đúng lỗi q17).
  - Cho phép chunk B nối sang trang kế khi một câu bị ngắt giữa hai trang, và lưu `page_end`.
  - Thêm tiền tố ngữ cảnh "Chương X › Mục Y" vào văn bản trước khi embed.
  - Thử hybrid dense + BM25 trên dev cho các câu hỏi chứa thuật ngữ (MCAR, HIPAA).
  - Đưa tuân thủ filter vào tiêu chí chọn, và viết thêm câu filter ở test.
