# 7. Kịch bản demo

## Chuẩn bị (trước buổi báo cáo 1 ngày)
1. Chạy server (local hoặc Render), đăng nhập admin, bấm **"Dịch + tạo audio toàn bộ"**, chờ độ phủ bản dịch đạt 100%.
2. Mở sẵn: tab GitHub Actions (1 lần chạy CI xanh + CD xanh), Swagger `/docs`, app du khách trên điện thoại (hoặc Chrome DevTools → Toggle device toolbar), dashboard admin.
3. Tạo sẵn 1 mã tiền mặt để phòng mạng chậm.

## Kiểm tra giữa kỳ — tuần 7 (≈ 10 phút)

| Phút | Nội dung | Người trình bày |
|---|---|---|
| 0–2 | Bài toán (PRD) + kiến trúc 3 lớp (sơ đồ README) | Danh |
| 2–5 | Mở code: đi theo 1 request `GET /pois/{id}` qua `content.py` → `ContentService` → `PoiRepository` | Mỗi người giải thích lớp mình |
| 5–7 | Swagger: login → tạo POI → xem trạng thái dịch 16 ngôn ngữ | Tài |
| 7–9 | `pytest` chạy 162 test; GitHub Actions: CI pipeline | Phát |
| 9–10 | Kế hoạch còn lại | Cả nhóm |

## Báo cáo cuối kỳ — tuần 11–12 (≈ 15 phút)

1. **Du khách mua vé online:** mở app → "Thanh toán online" → cổng giả lập → "Thanh toán thành công" → tự vào app.
2. **Đổi ngôn ngữ:** chọn 日本語 ở ô ngôn ngữ góc phải → giao diện + nội dung + audio đổi theo.
3. **Geofence:** tick **Giả lập GPS** → bấm vào vòng tròn "Cổng Tam Quan" → sau ~3 giây app tự mở và phát thuyết minh tiếng Nhật.
4. **Lộ trình:** tab Lộ trình → "Lộ trình cơ bản" → gợi ý thứ tự + quãng đường + thời gian.
5. **Chatbot AI:** hỏi *"Tượng Quan Âm cao bao nhiêu?"* → hỏi tiếp *"Nó được xây khi nào?"* (AI hiểu "nó" là tượng) → hỏi *"Giải giúp tôi bài toán"* → AI từ chối, gợi ý câu hỏi về chùa.
6. **Admin:** sửa nội dung 1 POI → app tạm hiển thị tiếng Việt kèm nhãn "chưa có bản dịch" → vài giây sau bản dịch mới xuất hiện (giải thích `source_hash`).
7. **Bán vé tiền mặt:** đăng nhập tài khoản staff → tạo mã → khách nhập mã. Staff thử xóa POI → bị chặn 403 (phân quyền).
8. **Dashboard giám sát:** doanh thu, độ phủ bản dịch, POI được quan tâm, câu hỏi gần đây.
9. **CI/CD:** tạo PR sửa 1 dòng → CI chạy → merge → CD deploy lên Render → mở link production.

## Câu hỏi vấn đáp thường gặp

- *Vì sao tách Service khỏi Router?* → test riêng được, đổi framework không ảnh hưởng nghiệp vụ, router mỏng dễ đọc.
- *Làm sao biết bản dịch đã cũ?* → `source_hash` (MD5 nội dung gốc lúc dịch) so với nội dung hiện tại.
- *Khách đi qua nhiều vùng chồng nhau?* → chọn theo `priority` rồi khoảng cách; debounce 3 giây; cooldown 5 phút.
- *Webhook giả mạo?* → chữ ký HMAC-SHA256 với secret chung, so sánh `hmac.compare_digest` chống timing attack; xử lý idempotent.
- *Mất mạng?* → app dùng bundle đã lưu trong `localStorage`; không có audio thì dùng giọng đọc của trình duyệt.
- *Test lớp API không cần DB thế nào?* → `app.dependency_overrides` thay Service bằng `AsyncMock`.
