# Nhãn chấm thủ công

Các file CSV do `python -m src.run` tạo ở dạng mẫu trống, sau đó được điền nhãn.

| File | Mẫu | Thang | Cách chấm |
|---|---|---|---|
| `coherence_labels.csv` | 10 vị trí × A/B/C. Vị trí = điểm giữa văn bản của 10 trang được tính đầu tiên (sắp theo source_id, page), chọn trước khi xem điểm | 0 = cắt giữa ý / thiếu chủ thể, 1 = hiểu một phần, 2 = tự hiểu được và trọn ý | Đọc chunk chứa vị trí đó. C dùng chung chunk với B nên cùng nhãn |
| `metadata_labels.csv` | 5 câu test × top-3 × A/B/C | yes/no: `document_id`, `source`, `page`, `chapter`, `section` đều đúng | Script đối chiếu text chunk với trang nguồn đã chuẩn hóa (trang, chương, mục theo vị trí heading), sau đó đọc lại các dòng báo lỗi |
| `grounding_labels.csv` | 5 câu test × A/B/C | 0 = không có bằng chứng, 1 = có nhưng thiếu điều kiện/ngữ cảnh, 2 = đủ để trả lời và truy nguồn | Đọc cả top-3 so với `expected_answer` và evidence |

**Người chấm:** nhãn coherence và grounding do Claude (AI) soạn nháp ngày 2026-11-13; học viên Nguyễn Sỹ Huy Kiên là người duyệt cuối. Cột `labeled_by` ghi rõ nguồn nhãn. Nguy cơ thiên lệch: chỉ một người duyệt, và người chấm biết chunk thuộc chiến lược nào. Đây là đánh giá **độ đủ của bằng chứng truy xuất**, không phải độ chính xác câu trả lời của LLM.
