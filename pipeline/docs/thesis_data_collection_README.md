# Kế hoạch thu thập dữ liệu — Tuần 1

## Trạng thái theo từng lớp tài sản (bảng 6.1 trong đề cương)

| Lớp tài sản     | Cách thu thập                          | Mức độ tự động | File/hướng dẫn |
|-----------------|------------------------------------------|-----------------|----------------|
| Cổ phiếu        | vnstock (VN-Index/VN30)                 | Tự động hoàn toàn | `00_collect_stock_data.py` |
| Bất động sản    | vnstock (VHM, NVL, KDH, DXG)             | Tự động hoàn toàn | `00_collect_stock_data.py` |
| Quỹ mở/ETF      | vnstock (E1VFVN30)                       | Tự động hoàn toàn | `00_collect_stock_data.py` |
| Vàng            | Scrape cafef.vn (cần verify endpoint)   | Semi-automation  | `01_collect_gold_price.py` |
| Tiền gửi        | Tải thủ công từ IMF IFS (UI, không có API tải trực tiếp) | Bán thủ công (1 lần) | `02_deposit_rate_guide.md` |
| Trái phiếu      | HNX Bond Market — **chưa làm**, cần xác định nguồn cụ thể | Chưa bắt đầu | Đợi bạn phản hồi nguồn |

## Thứ tự khuyến nghị thực hiện trong tuần 1

1. **Chạy `00_collect_stock_data.py` trước** — đây là phần chắc chắn chạy được, cho
   4/6 lớp tài sản chỉ trong vài phút. Làm việc này trước để có dữ liệu sớm, tránh
   dồn hết vào cuối tuần.
2. **Thử `01_collect_gold_price.py`** — nếu endpoint AJAX đã lỗi thời (khả năng
   khá cao vì cafef có thể đổi cấu trúc), làm theo hướng dẫn DevTools trong file
   để tìm endpoint mới, hoặc dùng phương án fallback đọc bảng HTML trực tiếp.
3. **Làm theo `02_deposit_rate_guide.md`** — đây là việc thủ công 1 lần trên UI
   của IMF, không cần code, chỉ mất khoảng 15-30 phút.
4. **Trái phiếu** — mình chưa có đủ thông tin để viết script/hướng dẫn cụ thể vì
   chưa xác định được HNX Bond Market có cung cấp API/trang tra cứu lịch sử công
   khai hay không. Bạn báo lại sau khi kiểm tra sơ bộ, hoặc mình tìm hiểu thêm khi
   bạn cần.

## Lưu ý quan trọng: chạy trên máy local, không chạy trong chat này

Toàn bộ 3 script/hướng dẫn trên đều cần internet truy cập được các trang dữ liệu
Việt Nam (cafef.vn, các API của vnstock, IMF Data Portal) — môi trường sandbox của
Claude trong cuộc trò chuyện này **bị chặn các domain này** (đã xác nhận cafef.vn
trả về lỗi 403 khi test), nên không thể chạy thử trực tiếp ở đây. Cần setup Python
local theo hướng dẫn đã gửi trước đó (venv + pip install), sau đó:

```bash
pip install vnstock requests pandas --break-system-packages
python 00_collect_stock_data.py
python 01_collect_gold_price.py
```

## Sau khi có đủ dữ liệu thô

Các file CSV trong `data/raw/` sẽ là input cho bước tiếp theo — chuẩn hóa tần suất
(daily -> monthly target, giữ features theo ngày như đã thống nhất ở mục 6.1 đề
cương) và merge thành 1 panel duy nhất (mục 6.1.1). Bạn báo khi có dữ liệu thô đầy
đủ, mình viết tiếp script chuẩn hóa + merge.
