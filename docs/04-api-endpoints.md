# 4. Danh sách API (49 endpoint)

Tài liệu tương tác đầy đủ (schema request/response, thử trực tiếp): **`/docs`** (Swagger) hoặc **`/redoc`**.

**Xác thực**
- API du khách: header `Authorization: Bearer <access_token>` lấy từ `POST /api/v1/access/token`.
- API admin: `Authorization: Bearer <token>` lấy từ `POST /api/v1/admin/auth/login`.
- Token admin cũng dùng được cho API du khách (để admin xem thử app).

**Định dạng phản hồi**
```json
{ "success": true,  "data": { ... }, "message": null }
{ "success": false, "error": { "code": "POI_NOT_FOUND", "message": "Không tìm thấy POI", "details": null } }
```

## Công khai & mua quyền truy cập

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/health` | Liveness: server còn sống |
| GET | `/health/ready` | Readiness: kết nối DB OK (503 nếu không) |
| GET | `/api/v1/languages` | Danh sách ngôn ngữ đang hỗ trợ |
| GET | `/api/v1/ui-strings/{lang}` | Nhãn giao diện app theo ngôn ngữ (tự dịch lần đầu, sau đó lưu DB) |
| GET | `/api/v1/access/info` | Giá và phương thức mua quyền truy cập |
| POST | `/api/v1/access/online` | Bắt đầu thanh toán online → nhận URL cổng thanh toán |
| POST | `/api/v1/access/token` | Đổi mã truy cập lấy access token (409 `PAYMENT_PENDING` nếu chưa thanh toán xong) |
| GET | `/api/v1/access/me` | Thông tin quyền truy cập hiện tại |
| POST | `/api/v1/payments/webhook` | Cổng thanh toán báo kết quả (header `X-Signature` HMAC-SHA256) |

## Du khách (cần access token)

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/v1/content/bundle?lang=ja` | Tải **toàn bộ** dữ liệu 1 lần; gửi `If-None-Match` → 304 nếu không đổi. Ngôn ngữ chưa dịch → tự xếp hàng dịch nền, header `X-Translation-Pending` = số điểm đang dịch (app tải lại đến khi = 0) |
| GET | `/api/v1/pois?lang=` | Danh sách POI theo ngôn ngữ (có fallback) |
| GET | `/api/v1/pois/nearby?lat=&lng=&radius=&lang=` | POI gần vị trí GPS, sắp xếp gần → xa |
| GET | `/api/v1/pois/{poi_id}?lang=` | Chi tiết 1 POI |
| POST | `/api/v1/pois/{poi_id}/localizations/{lang}/ensure` | Dịch + tạo audio ngay cho ngôn ngữ chưa có |
| GET | `/api/v1/tours?lang=` | Các lộ trình có sẵn |
| POST | `/api/v1/tours/recommend` | Gợi ý thứ tự tham quan từ vị trí hiện tại |
| POST | `/api/v1/chat` | Hỏi chatbot (429 nếu vượt giới hạn/ngày) |
| POST | `/api/v1/events` | Ghi nhận hành vi: `view`, `audio_play`, `geofence_enter` |

Mỗi POI trả về có `requested_lang`, `served_lang`, `is_fallback` để app biết đang hiển thị ngôn ngữ thay thế.

## Quản trị (cần token admin; ✏️ = chỉ role `admin`)

| Method | Đường dẫn | Mô tả |
|---|---|---|
| POST | `/api/v1/admin/auth/login` | Đăng nhập |
| GET | `/api/v1/admin/auth/me` | Tài khoản hiện tại |
| POST | `/api/v1/admin/auth/change-password` | Đổi mật khẩu |
| GET | `/api/v1/admin/pois?q=&is_active=&page=&size=` | Tìm/lọc POI (phân trang) |
| POST ✏️ | `/api/v1/admin/pois` | Tạo POI → tự xếp hàng dịch + tạo audio |
| GET | `/api/v1/admin/pois/{id}` | Chi tiết POI |
| PUT ✏️ | `/api/v1/admin/pois/{id}` | Sửa một phần; đổi tên/nội dung → tự dịch lại |
| DELETE ✏️ | `/api/v1/admin/pois/{id}` | Xóa (kèm bản dịch, gỡ khỏi tour) |
| GET | `/api/v1/admin/pois/{id}/localizations` | Trạng thái dịch/audio theo từng ngôn ngữ |
| POST ✏️ | `/api/v1/admin/pois/{id}/localize` | Xếp hàng dịch (`languages`, `force`) — 202 |
| PUT ✏️ | `/api/v1/admin/pois/{id}/localizations/{lang}` | Sửa tay bản dịch |
| POST ✏️ | `/api/v1/admin/localize-all` | Dịch toàn bộ POI + tour — 202 |
| GET / POST ✏️ | `/api/v1/admin/tours` | Danh sách / tạo lộ trình |
| PUT ✏️ / DELETE ✏️ | `/api/v1/admin/tours/{id}` | Sửa / xóa lộ trình |
| GET | `/api/v1/admin/languages` | Tất cả ngôn ngữ |
| PATCH ✏️ | `/api/v1/admin/languages/{code}` | Bật/tắt (không tắt được `vi`, `en`) |
| POST | `/api/v1/admin/access-codes` | Tạo mã tiền mặt (staff cũng dùng được) |
| GET | `/api/v1/admin/access-sessions?status=&page=&size=` | Lịch sử phiên truy cập |
| POST ✏️ | `/api/v1/admin/access-sessions/{id}/revoke` | Thu hồi quyền truy cập |
| GET / POST ✏️ | `/api/v1/admin/knowledge` | Bài viết kiến thức chatbot |
| PUT ✏️ / DELETE ✏️ | `/api/v1/admin/knowledge/{id}` | Sửa / xóa bài viết |
| GET | `/api/v1/admin/stats` | Số liệu dashboard giám sát |
| GET | `/api/v1/admin/chat-logs?limit=` | Câu hỏi gần đây |
| POST ✏️ | `/api/v1/admin/ai/enhance-description` | AI gợi ý viết lại mô tả (503 nếu chưa cấu hình LLM) |
| GET / POST ✏️ | `/api/v1/admin/users` | Danh sách / tạo tài khoản |
| PATCH ✏️ | `/api/v1/admin/users/{id}` | Sửa vai trò, khóa/mở, đặt lại mật khẩu |

## Ví dụ nhanh với curl

```bash
# Đăng nhập admin
curl -X POST localhost:8000/api/v1/admin/auth/login -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}'

# Tạo mã tiền mặt
curl -X POST localhost:8000/api/v1/admin/access-codes -H "Authorization: Bearer <ADMIN_TOKEN>" \
     -H "Content-Type: application/json" -d '{"quantity":1}'

# Du khách đổi mã lấy token rồi tải dữ liệu tiếng Nhật
curl -X POST localhost:8000/api/v1/access/token -H "Content-Type: application/json" -d '{"code":"AB3K9Q"}'
curl "localhost:8000/api/v1/content/bundle?lang=ja" -H "Authorization: Bearer <VISITOR_TOKEN>"
```
