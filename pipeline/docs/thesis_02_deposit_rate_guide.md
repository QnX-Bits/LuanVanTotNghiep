# Hướng dẫn thu thập dữ liệu Tiền gửi (lớp tài sản 4/6) — CẬP NHẬT

## Lịch sử quyết định (để bạn nắm bối cảnh khi đọc lại sau này)

1. Ban đầu định scrape website ngân hàng — **không khả thi** vì chỉ hiển thị
   lãi suất hiện tại, không lưu lịch sử.
2. Chuyển sang World Bank/IMF (`FR.INR.DPST`) — có lịch sử nhưng tần suất
   **năm** (không phải tháng) và dừng ở **2023** (thiếu 2024-2026).
3. Cân nhắc nội suy tuyến tính từ dữ liệu năm sang tháng — bị loại vì 3 hạn
   chế nghiêm trọng: (a) làm méo variance/correlation trong bài toán MVO,
   (b) look-ahead bias vi phạm nguyên tắc walk-forward, (c) feature ML vô
   nghĩa vì đường nội suy gần như hằng số.
4. Cân nhắc CEIC/Refinitiv qua thư viện UEH — lịch truy cập sớm nhất là
   tháng 11, quá trễ so với deadline 8 tuần.
5. **Quyết định cuối: scrape các bài báo "Lãi suất Vietcombank tháng X/20YY"**
   — đã xác nhận chuỗi bài này tồn tại đều đặn từ ít nhất 2020 đến nay (2026)
   trên vietnambiz.vn, dnse.com.vn, cafef.vn — cho dữ liệu THẬT theo tháng,
   không nội suy, không look-ahead bias.

## Cách thực hiện

Dùng script `02_collect_deposit_rate_monthly.py` — quy trình 2 bước cho mỗi
tháng: (1) tìm URL bài viết đúng tháng qua Google Custom Search API, (2) fetch
và trích số liệu lãi suất kỳ hạn 12 tháng bằng regex trên text đã làm sạch.

### Chuẩn bị trước khi chạy

1. Đăng ký Google Programmable Search Engine (miễn phí):
   https://programmablesearchengine.google.com/ — tạo 1 search engine mới,
   lấy `Search Engine ID` (CSE ID)
2. Lấy API key tại Google Cloud Console:
   https://console.cloud.google.com/apis/credentials — bật "Custom Search API"
3. Điền `GOOGLE_API_KEY` và `GOOGLE_CSE_ID` vào đầu file script
4. `pip install pandas requests beautifulsoup4 --break-system-packages`
5. Chạy: `python 02_collect_deposit_rate_monthly.py`

### Sau khi chạy — BẮT BUỘC kiểm tra thủ công

Script tự đánh dấu cột `needs_review = True` cho các tháng không trích được
số liệu (do bài viết không tồn tại, hoặc cách viết số liệu khác pattern
regex đã định nghĩa). Với các dòng này, bạn cần tự mở `source_url` và điền
tay giá trị lãi suất 12 tháng vào cột `deposit_rate_12m`.

Ước tính: khoảng 10-20% số tháng có thể cần chỉnh tay do sự đa dạng cách
viết giữa các nguồn báo khác nhau — vẫn nhanh hơn nhiều so với thu thập
thủ công 100% từ đầu.

## Nếu vẫn không đủ độ dài lịch sử cần thiết

Có thể kết hợp: dùng chuỗi bài báo tháng cho giai đoạn 2020-2026 (đã xác
nhận tồn tại), và dùng dữ liệu World Bank/IMF theo năm cho giai đoạn trước
2020 (nếu đề tài cần lùi xa hơn) — chỉ áp dụng nội suy cho phần lịch sử xa,
ít ảnh hưởng tới kết quả out-of-sample chính (thường nằm ở giai đoạn gần
đây nhất), và nêu rõ trong đề cương/luận văn đây là giới hạn có chủ đích.

