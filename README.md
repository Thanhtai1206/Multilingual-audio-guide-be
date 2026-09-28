# 🌐 Hệ Thống Thuyết Minh Tự Động Đa Ngôn Ngữ - Backend Service

## 📖 Tổng quan Đề tài
Đồ án **"Thuyết minh tự động đa ngôn ngữ"** được phát triển nhằm cung cấp giải pháp công nghệ backend mạnh mẽ, phục vụ việc quản lý, xử lý và phân phối nội dung thuyết minh tự động bằng nhiều ngôn ngữ khác nhau cho các hệ thống tham quan, bảo tàng và du lịch thông minh.

## ⚙️ Trách nhiệm & Vai trò của Nhóm (Phần 2: Backend Development)
Nhóm chúng tôi chịu trách nhiệm chính trong việc phát triển và vận hành hệ thống Backend theo các tiêu chuẩn kỹ thuật sau:
* **Kiến trúc 3 lớp (3-Tier Architecture):** Xây dựng mã nguồn phân tầng rõ ràng (Presentation/Controller Layer, Business Logic Layer, Data Access Layer) giúp mã nguồn dễ bảo trì, mở rộng và tách biệt các tầng xử lý dữ liệu.
* **Quy trình CI/CD:** Tích hợp tự động hóa quy trình kiểm thử, build và triển khai ứng dụng, đảm bảo tính ổn định và tốc độ cập nhật mã nguồn liên tục lên môi trường chạy thực tế.
* **Xử lý API & Dữ liệu đa ngôn ngữ:** Thiết kế các API RESTful hiệu suất cao phục vụ việc tra cứu, đồng bộ hóa nội dung thuyết minh và quản lý thông tin đa ngôn ngữ cho hệ thống client.

## 📂 Cấu Trúc Thư Mục
* `/frontend`: Tầng giao diện người dùng (xây dựng bằng React.js cho Web hoặc React Native) có nhiệm vụ hiển thị thông tin, nhận thao tác chạm/chọn từ người dùng và gửi request đến Backend.
* `/backend`
* `/database`: Nơi lưu trữ toàn bộ dữ liệu của hệ thống (như thông tin các điểm tham quan, nội dung thuyết minh đa ngôn ngữ, dữ liệu vector cho AI), mà phần tầng dao (Data Access Layer) trong Backend sẽ kết nối vào để truy vấn.
* `/docs`: Lưu trữ tài liệu thiết kế và báo cáo đồ án của nhóm.

## 📂 Cấu Trúc Thư Mục Backend (3 Lớp & CI/CD)
* `/src/main/java/controller` (Presentation Layer): Tiếp nhận HTTP Request từ client và trả về kết quả API.
* `/src/main/java/service` (Business Logic Layer): Xử lý toàn bộ logic nghiệp vụ của hệ thống thuyết minh tự động.
* `/src/main/java/dao` (Data Access Layer): Chứa các thành phần kết nối và truy vấn cơ sở dữ liệu.
* `.github/workflows`: Chứa các file cấu hình tự động hóa CI/CD (GitHub Actions).
* `/docs`: Lưu trữ tài liệu thiết kế và báo cáo đồ án của nhóm.

## 👥 Thành Viên Nhóm
* **Trương Công Danh**
* **Võ Thành Tài**
* **Nguyễn Lê Tấn Phát**
