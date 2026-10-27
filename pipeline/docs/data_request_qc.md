# Đóng 5 cờ QC còn lại — checklist

> **Trạng thái 24/10/2026: ĐÃ ĐÓNG CẢ 5 CỜ** (panel 02/2016–07/2026, 126 tháng; xem SUA_LOI.md đợt 5). Phần dưới giữ lại
> làm hướng dẫn cập nhật dữ liệu về sau.

Toàn bộ code đã sẵn sàng: mỗi file dưới đây có mặt trong `data/raw/` thì nhánh xử lý tương ứng **tự bật**,
không phải sửa code. Các bước tải phải làm trên **máy của bạn** (sandbox của Claude bị chặn các trang dữ liệu
Việt Nam). **Một lệnh cho tất cả phần tự động:** `python scripts/collect_all.py` (giá cổ phiếu, tỷ giá, JSON pricedancing → file thô,
NAV quỹ trái phiếu; cuối cùng in việc còn phải làm tay). Kiểm tra bất cứ lúc nào bằng:

    python scripts/00_check_raw_data.py      # in [OK]/[FLAG] dự kiến cho từng cờ + độ dài panel/giai đoạn kiểm tra

Đã chạy thử toàn bộ pipeline với dữ liệu GIẢ LẬP đúng định dạng các file này (2014–2026): panel 11/2014–07/2026
(141 tháng), giai đoạn kiểm tra 11/2016–07/2026 (117 tháng), `19_qc_checks.py` không còn cờ dữ liệu.

---

## Cờ 1 — mẫu ≥ 120 tháng (hiện 78) · làm cùng cờ 4 và bước 6

Panel bắt đầu ở tháng sớm nhất mà **cả 5 lớp** đều có dữ liệu. Hiện trái phiếu, vàng, tiền gửi cùng chặn ở 02/2020;
ETF có từ 10/2014 nên mốc tốt nhất có thể đạt là **11/2014 → 141 tháng**.

| Bước | Dữ liệu | Cách lấy | Lệnh |
|---|---|---|---|
| 1a | Giá ngày VNINDEX, E1VFVN30, KDH, DXG, NVL, VHM + ứng viên rổ BĐS, từ 2014 | **Không dùng vnstock** (gói vnstock/vnai bị PyPI cách ly 10/2026): script gọi thẳng API VCI → VNDirect → TCBS bằng `requests`, mỗi mã lấy cả chuỗi 2014–nay từ một nguồn | `python scripts/00_collect_stock_data.py` |
| 1a' | (dự phòng) | investing.com → trang "Historical Data" của mã → chọn 01/01/2014 → Download | `python scripts/02c_convert_investing_csv.py stock E1VFVN30 "<file>.csv"` |
| 1b | Lợi suất TPCP 5 năm từ 2014 | investing.com "Vietnam 5-Year Bond Yield Historical Data" (nguồn của file hiện tại) → chọn 01/01/2014 → Download | `python scripts/02c_convert_investing_csv.py bond VN5Y "<file>.csv"` |
| 1c' | Lãi tiền gửi 12 tháng 2014–06/2020 | **Đã có**: `02d_build_vcb_term_rates.py` bổ sung từ bảng mốc Vietcombank (cùng ngân hàng với chuỗi pricedancing). Tiền gửi không còn chặn mốc panel; còn trái phiếu và vàng | — |
| 1c | Vàng SJC (+ lãi tiền gửi 12 tháng nếu muốn thay số VCB) trước 2020 | pricedancing.com, period **"Tất cả"** (all-time: vàng có từ 2009). Lấy JSON như lần trước (DevTools → request `/api/chart/rAAvxj?...period=all-time` và `btQhHe`, kèm bản `4y`), lưu vào `data/raw/pricedancing/` với tên `gold_alltime.json`, `gold_4y.json`, `deposit_12m_alltime.json`, `deposit_12m_4y.json`. File cũ đã bị cắt từ 2020, dữ liệu xa hơn vốn có sẵn trong JSON | `python scripts/02b_build_raw_from_pricedancing.py` |
| 1d | Bật vàng point-in-time | Mở `settings.json`, đặt `"gold_vintage": 1` (xem bước 6) | — |

## Cờ 2c — tỷ giá USD/VND theo tháng — **ĐÃ ĐÓNG (24/10/2026)**

`python scripts/01d_collect_imf_usdvnd.py` tải IMF IFS (bản chép GitHub của codeforIATI, chạy được cả trong
sandbox) → `usd_vnd_monthly.csv` 01/2010–07/2026, bình quân tháng. Đây là tỷ giá **chính thức** (trung tâm NHNN);
nêu trong luận văn rằng chênh lệch thị trường–trung tâm nằm trong phần chênh lệch SJC. Phần dưới chỉ cần nếu muốn
thay bằng nguồn khác.

Dùng để tách basis của vàng thành tỷ giá × (1 + chênh lệch SJC); phần nội suy giữa các neo khi đó chỉ còn là
chênh lệch SJC, đúng như QC đề xuất.

- Nguồn nên trích dẫn: **IMF IFS** (data.imf.org → Exchange Rates → Vietnam → *Domestic currency per U.S. dollar,
  period average*, tần suất tháng → Export CSV). Thay thế: NHNN (tỷ giá trung tâm, có từ 2016); investing.com
  "USD VND Historical Data" (chọn Monthly).
- Cần phủ từ ít nhất 7 tháng trước đầu panel (≈ 04/2014).
- File `data/raw/usd_vnd_monthly.csv`, cột `date,usd_vnd` (bình quân tháng, date = ngày 1). Từ investing.com:
  `python scripts/02c_convert_investing_csv.py usdvnd USDVND "<file>.csv"`.

## Cờ 4 — cổ phiếu BĐS không chọn bằng hiểu biết năm 2026

Chọn **một** trong hai:

**A. Chỉ số ngành.** `00_collect_stock_data.py` thử tải chỉ số VNREAL vào `realestate_index_candidate.csv`. Nếu lịch
sử có từ 2014, đổi tên thành `realestate_index.csv` (cột `date,close`). Nguồn khác có cùng định dạng:
`python scripts/02c_convert_investing_csv.py reindex VNREAL "<file>.csv"`.

**B. Rổ point-in-time** (dùng khi không có chỉ số đủ dài). Quy tắc chốt TRƯỚC, ghi vào luận văn:

> Đầu mỗi năm N, rổ gồm 4 doanh nghiệp phát triển BĐS dân dụng có vốn hóa lớn nhất HOSE tại phiên cuối năm N−1;
> loại VIC (tập đoàn đa ngành), loại BĐS khu công nghiệp và bán lẻ; bình quân đều trong năm.

1. Lập bảng vốn hóa cuối mỗi năm 2013–2025 (cafef.vn / vietstock.vn mục xếp hạng vốn hóa, hoặc tự tính
   = giá đóng cửa × số cổ phiếu lưu hành từ BCTC). Lưu lại bảng gốc làm phụ lục.
2. Ghi `data/raw/re_basket_membership.csv`, cột `year,symbol`, mỗi năm 4 dòng (mẫu:
   `re_basket_membership_TEMPLATE.csv`). Rổ tự xử lý chuyện mã niêm yết muộn (NVL 12/2016, VHM 05/2018).
3. Mọi mã trong bảng phải có giá ngày trong `all_stock_based_raw.csv`. `00_collect_stock_data.py` đã tải sẵn danh
   sách ứng viên (`RE_CANDIDATES`); thêm mã vào danh sách đó nếu thiếu.

Khi có A hoặc B, lớp BĐS chuyển sang mã `RE_BASKET`; 4 mã cũ vẫn còn trong panel cho trang thị trường của app.

## Cờ 5b — lãi suất kỳ hạn ngắn + trích dẫn nguồn — **ĐÃ ĐÓNG (24/10/2026)**

Chuỗi 12 tháng của pricedancing đã xác định là **Vietcombank, tại quầy, KHCN**: 44/48 tháng giá thật khớp tuyệt đối
với bảng mốc điều chỉnh của VCB, 4 tháng còn lại lệch 0,1–0,2 điểm do ngày hiệu lực giữa tháng. Lãi kỳ hạn 1/3 tháng
lấy từ ~50 bài báo đưa tin các lần VCB đổi biểu lãi suất 2014–2026:
`data/raw/vcb_deposit_rate_events.csv` (URL từng mốc) → `python scripts/02d_build_vcb_term_rates.py` →
`deposit_rate_1m_3m.csv`. Khoảng còn chưa xác minh: 01–08/2016 (`vcb_step_unverified_gap`; lãi 12T 01/2015–08/2016
ghi `vcb_news_step_unverified`); có thể bổ sung mốc vào file events rồi chạy lại 02d. Các bước dưới chỉ cần nếu muốn
thay bằng chuỗi pricedancing (02b ưu tiên pricedancing, giữ số VCB cho tháng thiếu).

1. **Trích dẫn**: mở biểu đồ "Tiền gửi 12 tháng" trên pricedancing.com (chart `btQhHe`), xác định chuỗi là của ngân
   hàng hay nhóm nào; đối chiếu 3–4 tháng với biểu lãi suất niêm yết của ngân hàng đó (chuỗi hiện có: 7,4% đầu 2023;
   4,6–4,7% giai đoạn 2024–2025). Điền dòng `deposit_rate_12m` trong `data/raw/SOURCES.md`.
2. **Kỳ hạn 3 tháng**: pricedancing chart `VjbhHe` (đã xác nhận có) → lưu `deposit_3m_4y.json`,
   `deposit_3m_alltime.json` vào `data/raw/pricedancing/`.
3. **Kỳ hạn 1 tháng**: tìm chart 1 tháng trong DevTools trên cùng trang (nếu có) → `deposit_1m_*.json`. Nếu trang không
   có, lấy từ các bài "Lãi suất Vietcombank tháng X/YYYY" bằng `02_collect_deposit_rate_monthly.py` (đổi regex
   `12\s*tháng` thành `1\s*tháng`), rồi ghi cột `rate_1m`.
4. `python scripts/02b_build_raw_from_pricedancing.py` → `data/raw/deposit_rate_1m_3m.csv` (`date,rate_1m,rate_3m`).
   Engine tự dùng lãi kỳ hạn thực cho phần tiền mặt (tái cân bằng tháng → 1T, quý → 3T, năm → 12T); tháng nào
   thiếu mới dùng lại giả định chênh lệch 2,5 / 2,2 điểm %.

## Cờ 6 — NAV quỹ trái phiếu mở

    python scripts/01c_collect_fmarket_nav.py --list          # quỹ trái phiếu trên Fmarket + ngày phát hành
    python scripts/01c_collect_fmarket_nav.py --fund <MÃ>     # -> data/raw/bond_fund_nav.csv

Chọn quỹ có **ngày phát hành sớm nhất** và danh mục chủ yếu trái phiếu chính phủ/ngân hàng (quỹ nặng trái phiếu
doanh nghiệp chịu cú sốc 2022 riêng — nêu trong luận văn). Tháng trước ngày có NAV vẫn dùng chuỗi tổng hợp (cờ
`data_quality` ghi rõ). Nếu API đổi: mở trang quỹ trên fmarket.vn → DevTools → request `get-nav-history` → lưu
Response thành JSON → `--from-json <file>`. Điền tên quỹ vào `SOURCES.md`.

## Bước 6 — vì sao phải bật vàng point-in-time

Giá SJC hàng tháng thật chỉ có từ 08/2022; trước đó là neo 4 tháng. Nếu tháng quyết định d nằm giữa hai neo, giá
"dựng lại" tại d đã dùng neo SAU d → look-ahead. Bản hiện tại tránh bằng cách bắt đầu kiểm tra từ 09/2022, nên **kéo
dài panel mà không bật chế độ này thì giai đoạn kiểm tra vẫn chỉ 47 tháng**. Với `"gold_vintage": 1`, tháng t chỉ
dùng các neo ≤ t (basis giữ nguyên sau neo gần nhất) để ước lượng rủi ro và làm feature ML; lợi nhuận thực hiện vẫn
dùng chuỗi dựng lại cuối cùng (`tests/test_gold_vintage.py` kiểm tra: đổi một neo tương lai không làm đổi tỷ trọng).
Phương án tốt hơn nếu tìm được: **giá SJC hàng tháng thật 2014–2022** (ghi `data_quality` = `real_monthly`) — khi đó
không cần dựng lại.

## Sau khi đủ dữ liệu

    python scripts/00_check_raw_data.py          # mọi dòng [OK]
    python run.py --stage all --no-open          # ~15–20 phút
    python -m pytest tests
    python scripts/19_qc_checks.py               # không còn [FLAG] dữ liệu
    python scripts/99_verify_reproducibility.py --update

Kết quả sẽ đổi (panel dài hơn, giai đoạn kiểm tra gồm 2018 và 2020–2022). Test backend đang ghim số của bản hiện tại
(`backend/tests/test_source_data.py`, `test_api_security.py`) và TODO.md cần cập nhật theo số mới.
