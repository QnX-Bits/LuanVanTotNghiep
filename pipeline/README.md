# Đồ án: Tối ưu hóa danh mục đa tài sản cho nhà đầu tư Việt Nam — pipeline nghiên cứu

## Chạy nhanh (không chạy lại mô hình)
    pip install -r requirements.txt
    python run.py
→ build `app/portfolio_app.html` từ `data/processed/*.csv` và mở trình duyệt (1 file, mở offline).

## Chạy lại
    python run.py --stage backtest     # 11 → 15 → 14 → 12 → 13 → 16 → 18 → 19 (~1 phút)
    python run.py --stage forecasts    # thêm 06, 07 (dự báo ML ngoài mẫu, ~2 phút) trước backtest
    python run.py --stage all          # thêm 03, 04 (panel) + 17 (mô phỏng bootstrap, ~10 phút)
    python run.py --stage simulation   # chỉ 17
    python -m pytest tests             # 28 test: BL/RP/HRP/MVO, look-ahead (kể cả vàng point-in-time), dữ liệu
    python scripts/99_verify_reproducibility.py   # so checksum đầu ra với expected_checksums.json
Bước 00–02c (thu thập/chuyển đổi: vnstock, pricedancing, World Bank, Fmarket, investing.com) chạy tay trên máy có
mạng; dữ liệu thô có sẵn trong `data/raw/`. **Thu thập dữ liệu còn thiếu: `python scripts/collect_all.py`** (chi tiết: `docs/data_request_qc.md`), kiểm tra
bằng `python scripts/00_check_raw_data.py`. File nào có mặt trong `data/raw/` thì nhánh xử lý tự bật:

| File / thiết lập | Tác dụng |
|---|---|
| dữ liệu thô dài hơn | `PANEL_START` tự lùi về tháng sớm nhất cả 5 lớp đều có (ép bằng `PVN_PANEL_START`) |
| `usd_vnd_monthly.csv` | basis vàng = tỷ giá × (1 + chênh lệch SJC); tạo bằng `01d_collect_imf_usdvnd.py` (IMF IFS) |
| `realestate_index.csv` / `re_basket_membership.csv` | lớp cổ phiếu BĐS = mã `RE_BASKET` (chỉ số ngành / rổ point-in-time) |
| `deposit_rate_1m_3m.csv` | tiền mặt hưởng lãi kỳ hạn 1/3 tháng thực (Vietcombank, dựng bằng `02d_build_vcb_term_rates.py` từ `vcb_deposit_rate_events.csv`) |
| `bond_fund_nav.csv` | trái phiếu = NAV quỹ trái phiếu mở |
| `settings.json` → `"gold_vintage": 1` | vàng point-in-time (mã `GOLD_SJC_RT`) → giai đoạn kiểm tra không phải chờ 08/2022 |
| `data/raw/SOURCES.md` | trích dẫn nguồn từng file (QC 5) |

## Thiết kế sau QC đợt 5 (chi tiết: `SUA_LOI.md`)
- **Panel** 02/2016–07/2026 (126 tháng, 11 mã). Giai đoạn kiểm tra: return 02/2018–07/2026 (102 tháng); vàng dùng
  chế độ point-in-time (`gold_vintage = 1`) nên không quyết định nào dùng neo giá vàng tương lai.
- **5 lớp**: cổ phiếu (thực hiện qua ETF E1VFVN30), cổ phiếu BĐS (`RE_BASKET`: 4 DN BĐS dân dụng vốn hóa lớn nhất
  HOSE cuối năm trước, bình quân đều), vàng SJC, trái phiếu (NAV quỹ DCBF; lợi suất TPCP 5 năm cho biến kinh tế),
  tiền gửi Vietcombank = **tiền mặt nhận phần dư**. VN-Index chỉ là chuỗi tham chiếu. Bản 6 lớp gốc chạy ở độ nhạy.
- **Trần 50%/lớp** cho mọi phương pháp (MVO/BL trong cvxpy; EW/RP/HRP sau phép chiếu dải, phần vượt của lớp phòng
  thủ chuyển về tiền gửi).
- **Vàng** trước 08/2022: dựng lại = vàng thế giới (World Bank) × 1,20565 × basis, basis nội suy giữa các
  neo thật (`data_quality` = `reconstructed_*`); kiểm chứng ở `gold_reconstruction_validation.csv`.
- **Quy ước thời gian**: quyết định cuối tháng t chỉ áp cho return tháng t+1; lãi tiền gửi/carry trái phiếu
  của tháng t dùng lãi suất cuối tháng t−1.
- **Ước lượng chung** mọi khung thời gian: EWMA half-life 18 tháng trên toàn bộ lịch sử + Ledoit–Wolf co
  tương quan; trái phiếu khử độ trơn (Geltner). Khung thời gian chỉ đổi tần suất tái cân bằng (1/3/12 tháng)
  và kỳ hạn phần tiền mặt.
- **Khẩu vị** = dải tỷ trọng nhóm rủi ro (cổ phiếu + cổ phiếu BĐS): Thận trọng 10–30%, Cân bằng 40–60%,
  Tăng trưởng 70–90%. MVO/BL/MLP_MVO: ràng buộc trong cvxpy. EW/RP/HRP: thiết kế hai tầng (vol mục tiêu
  5/10/16% + dải; phương pháp quyết định tỷ lệ trong nhóm).
- **Markowitz**: μ Bayes–Stein (Jorion 1986), δ = 2,5, trần 50%/lớp, phạt turnover, Clarabel.
- **Black–Litterman**: π = δΣw_EW; view ML chỉ cho lớp có R²_OS > 0 ngoài mẫu tại thời điểm quyết định, mức
  tin cậy = trọng số kết hợp tối ưu λ* (kiểu Idzorek); không view cho tiền gửi và trái phiếu tổng hợp.
- **ML** (06, 07): dự báo ngoài mẫu hàng tháng, cửa sổ mở rộng, target chia vol, trung bình lớp nằm ngoài mô
  hình; ENet (đường alpha đầy đủ), LightGBM (lưới nông, 1-SE, tune lại mỗi 12 tháng), MLP (dừng sớm theo
  thời gian, 5 seed). Đánh giá: R²_OS theo lớp, Clark–West, rank IC.
- **Kiểm định** (12): Ledoit–Wolf 2008, Holm theo họ H1/H2/H3 (H4/RL ở phụ lục), ngưỡng phát hiện, Deflated
  Sharpe. Mô phỏng stationary bootstrap (17). Phân rã đóng góp (18). Đối chiếu QC (19).
- **Phí** theo lớp: cổ phiếu/ETF/BĐS 0,20%, vàng 1,0%, tiền gửi/trái phiếu 0,30% (`PVN_TRANSACTION_COST`
  → phí đồng nhất).
- **App tư vấn** dùng Risk Parity, tỷ trọng `allocation_current.csv` = quyết định trên dữ liệu tới 07/2026.

## Biến môi trường (độ nhạy / admin run)
`PVN_DELTA` (2,5), `PVN_EWMA_HALFLIFE` (18), `PVN_ROLLING_WINDOW` (0 = EWMA), `PVN_RF_SHIFT` (0),
`PVN_CASH_HAIRCUT` (1), `PVN_TRANSACTION_COST` (trống = theo lớp), `PVN_GOLD_RECON` (1), `PVN_BOND_VIEWS` (0),
`PVN_N_BOOT_HIST` (1000), `PVN_N_JOBS` (2), `PVN_GOLD_VINTAGE` (theo `settings.json`), `PVN_PANEL_START` (tự động).

## Cấu trúc
    run.py            điểm vào duy nhất (đặt 1 luồng BLAS để tái lập)
    SUA_LOI.md        nhật ký sửa lỗi + số liệu trước/sau (đợt 1-4)
    scripts/          00-19: pipeline; common.py: hằng số & hàm chung; backtest_engine.py: walk-forward
                      09: ước lượng + tối ưu; 10: Black-Litterman; 99: kiểm tra tái lập
    tests/            pytest (tối ưu, look-ahead, dữ liệu)
    data/raw/         dữ liệu thô (+ world_gold_usd_monthly_wb.csv)
    data/processed/   kết quả trung gian & cuối (qc_checks.csv: trạng thái từng mục QC)
    app/              build_app.py + template.html → portfolio_app.html
    docs/             đề cương, hướng dẫn thu thập, data_request_qc.md
