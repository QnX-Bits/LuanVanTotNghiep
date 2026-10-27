# Nhật ký sửa lỗi chí mạng (05/10/2026)

Toàn bộ pipeline (bước 03 → 15 và app) đã được chạy lại sau khi sửa. Số liệu ở `data/processed/` và trong app là số mới.

## 1. Look-ahead bias (dùng thông tin tương lai) — RL, Black-Litterman, MLP
**Lỗi:** đặc trưng đo ở cuối tháng t (momentum_21d tương quan 0.59 với return cùng tháng) dùng để chọn tỷ trọng, rồi nhân với return của *chính tháng t*.
**Sửa:** tỷ trọng quyết định tại cuối tháng t chỉ áp cho return tháng t+1 (`common.forward_returns`). Sửa ở 08, 10, 11, 12, 14, 15.
**Kiểm chứng:** xáo trộn toàn bộ dữ liệu sau thời điểm quyết định 2023-09 → tỷ trọng BL thay đổi tối đa 3·10⁻⁹ (sai số làm tròn).
**Tác động:** RL từ phương pháp tốt nhất (Sharpe thô 0.78) xuống ngang các phương pháp khác (Sharpe vượt trội −0.31). Lợi thế cũ của RL hoàn toàn do look-ahead.
Giai đoạn ngoài mẫu dịch 1 tháng: 2022/08 → 2025/01 (30 tháng).

## 2. Sharpe không trừ lãi suất phi rủi ro
**Lỗi:** Sharpe = mean/std của return thô, trái với định nghĩa ở mục 6.2 đề cương.
**Sửa:** Sharpe và JK-Memmel tính trên return vượt trội so với lãi tiền gửi 12 tháng (`common.sharpe`, `common.excess`). App hiển thị thêm lãi tiền gửi cùng kỳ.

| Cân bằng / Trung hạn | Sharpe cũ (thô) | Sharpe mới (vượt trội) | Lợi nhuận/năm cũ | mới | Tiền gửi cùng kỳ |
|---|---|---|---|---|---|
| HRP | 0.65 | −0.13 | 4.1% | 3.7% | 5.8% |
| Equal Weight | 0.23 | −0.18 | 2.1% | 2.5% | 5.8% |
| Risk Parity | 0.21 | −0.19 | 1.4% | 3.0% | 5.8% |
| Markowitz | 0.06 | −0.06 | −0.3% | 3.3% | 5.8% |
| Black-Litterman | 0.18 | −0.34 | 1.4% | 0.0% | 5.8% |

**Kết luận phải viết trong Chương 4:** giai đoạn 2022/08–2025/01, không phương pháp đa tài sản nào thắng gửi tiết kiệm 12 tháng ở khẩu vị Cân bằng; Sharpe vượt trội dương chỉ xuất hiện ở khẩu vị Thận trọng: HRP 0.11–0.16 và Markowitz 0.12–0.17 tùy khung thời gian, BL ngắn hạn 0.06; mọi kịch bản Cân bằng và Tăng trưởng đều âm.

## 3. Khẩu vị rủi ro không có tác dụng trong app tư vấn
**Lỗi:** chỉ có trần tỷ trọng nhóm rủi ro (30/60/90%). HRP chỉ để ~2% vào nhóm rủi ro nên không bao giờ chạm trần → 3 khẩu vị cho cùng một danh mục (nhà đầu tư "Tăng trưởng" nhận 0.8% cổ phiếu).
**Sửa:** dải [sàn, trần]: Thận trọng 10–30%, Cân bằng 40–60%, Tăng trưởng 70–90% (`common.RISK_BANDS`, `apply_risk_band`), giữ nguyên tỷ lệ bên trong mỗi nhóm do phương pháp gốc quyết định.
**Tác động:** HRP dài hạn: nhóm rủi ro 2.1% / 2.1% / 2.1% → 10% / 40% / 70%. App ghi rõ dải đang áp dụng và cảnh báo khi danh mục thua tiền gửi.

## 4. Kiểm định H2 so sánh không cùng điều kiện
**Lỗi:** BL-ElasticNet có áp trần 60%, BL-LightGBM không áp gì (độ lệch chuẩn 0.033 vs 0.062); MLP_MVO cũng không áp; turnover tính khác nhau; nhãn "H2" không khớp đề cương.
**Sửa:** một hàm BL dùng chung (`11.compute_bl_mu_for_window(model_factory=...)`) cho ElasticNet/LightGBM/TabPFN, cùng dải khẩu vị, cùng thời điểm, cùng turnover. MLP_MVO áp cùng dải. Bảng Holm gắn nhãn giả thuyết theo mục 4.2: H2 = BL (ML) vs Markowitz (trung bình lịch sử); so sánh nguồn views = "H2 (bổ sung)". TabPFN tự động tham gia nếu môi trường có thư viện + HF_TOKEN.
**Tác động:** BL-ElasticNet vs BL-LightGBM: std 0.040 vs 0.047; Sharpe vượt trội −0.34 vs −0.15; p = 0.26.

## 5. Return trái phiếu thiếu lãi coupon (carry)
**Lỗi:** chỉ tính thay đổi giá −D·Δy + ½C·Δy² → TPCP 5 năm có return trung bình −1.57%/năm.
**Sửa:** cộng carry = lợi suất đầu tháng/12 (bước 03). Return trung bình mới +0.85%/năm (lợi suất trung bình 2.46%, giai đoạn lợi suất tăng).

## Kết quả kiểm định sau sửa
0/27 cặp có ý nghĩa sau Holm-Bonferroni (alpha 0.10); bootstrap đối chiếu cũng 0/27 (bản cũ: 3/27, đều là cặp "vs RL" — do look-ahead).

## Sửa kèm (nhỏ, cần để chạy đúng)
- 06: import TabPFN tại chỗ → thiếu thư viện chỉ bỏ qua TabPFN, không làm dừng `--stage all`.
- 07: sửa đường dẫn file so sánh → chạy lại không còn ghi đè mất bảng 4 mô hình.
- `requirements.txt` ghim phiên bản; xóa code chết ở 03; Sharpe thống nhất ddof=1.

## Đã chuyển sang đợt 2 (xem bên dưới)
Giai đoạn OOS mới 30 tháng (bỏ phí dữ liệu đến 2026/08); kịch bản khung thời gian gần như trùng nhau ở fold đầu; purge 6 tháng làm tỷ trọng tĩnh bị cũ; app hiển thị tỷ trọng trung bình lịch sử thay vì tỷ trọng tính trên dữ liệu mới nhất; giá vàng nội suy 2020–2022; Ω trong mẫu; δ không nhất quán; sàn biến động tiền gửi 5%; ánh xạ "Trên 5 năm" ↔ cửa sổ 36 tháng.

---

# Đợt 2 — nhóm lỗi phương pháp (06/10/2026)

## Backtest
- **Walk-forward hàng tháng** (`backtest_engine.py`) thay cho 5 fold × 6 tháng: giai đoạn ngoài mẫu 07/2023–08/2026 (38 tháng, trước đây 30 tháng và dừng ở 01/2025).
- **Bỏ purge 6 tháng ở cấp danh mục**: cửa sổ ước lượng kết thúc đúng tại tháng quyết định (trước đây tỷ trọng cũ 6–12 tháng). Purging chỉ giữ cho tune mô hình ML.
- **Khung thời gian thật sự khác nhau** (mục 6.5): 12T/hàng tháng, 24T/hàng quý, 36T/hàng năm; mọi kịch bản chung giai đoạn kiểm tra, cửa sổ luôn đủ độ dài. Tỷ trọng trôi theo giá giữa các lần tái cân bằng, turnover tính trên tỷ trọng đã trôi.
- **RL và MLP_MVO chạy cùng engine** với 5 phương pháp chính (cùng tháng, cùng dải khẩu vị, cùng phí).

## Bộ tối ưu (lỗi có từ bản gốc)
- **Markowitz thất bại ~50% số lần và lặng lẽ trả về Equal Weight**: hàm mục tiêu theo đơn vị tháng (~1e-3) nhỏ hơn dung sai SLSQP. Sửa: nhân hệ số tỷ lệ, gradient giải tích, nhiều điểm xuất phát. Kiểm chứng: không lời giải ngẫu nhiên nào tốt hơn.
- **Risk Parity không đạt đóng góp rủi ro bằng nhau** (lệch tới 0.17). Sửa: công thức lồi Maillard–Roncalli–Teïletche (2010); lệch còn < 1e-7.
- Trần 50%/tài sản bỏ khi universe chỉ có 2 tài sản (H3) — trước đây ép Markowitz/BL về đúng 50/50.
- Hiệp phương sai ước lượng theo cặp + chiếu về ma trận PSD.

## Dữ liệu
- **Neo giá vàng bị gắn sai 3 tháng**: điểm "4 tháng" là giá ĐÓNG CỬA cuối nến (bằng chứng: neo 2022-05 = 66,25 triệu = đúng giá đóng cửa 08/2022). Gắn lại đúng ngày, bỏ nội suy; tháng thiếu để trống. Biến động tháng của vàng: 1,6% (nội suy) → 5,3% (thật).
- **Neo tiền gửi lệch 1 tháng** (cùng lý do): gắn lại, giữa 2 neo dùng giá trị trước đó (lãi suất là hàm bậc thang).
- **Bỏ VN30** khỏi lớp cổ phiếu (tương quan 0,96 với VN-Index, 0,99 với ETF). Rổ BĐS giữ bình quân đều — lý do ghi trong 03 (không có dữ liệu cổ phiếu lưu hành; theo vốn hóa thì rổ ≈ VHM).

## Black-Litterman (đúng mục 6.4.3)
- Ω = EWMA (λ=0,9) của lỗi dự báo NGOÀI MẪU; 12 kỳ burn-in trước giai đoạn kiểm tra; lớp chưa đủ 12 lỗi thì không đưa view (P chọn một phần lớp tài sản).
- δ từ Sharpe của EW trên return vượt trội, chặn [1, 10], dùng chung cho prior và MVO (không view → đúng EW). Q tính theo return vượt trội.
- ElasticNet tune nội bộ cửa sổ bằng chia theo tháng có khoảng đệm 1 tháng. Chẩn đoán δ/Q/Ω từng lần: `bl_diagnostics.csv`.

## Mô hình dự báo
- **Nested purged CV** (06, 07): tham số chọn ở vòng trong chỉ trên tập train của từng fold ngoài; vòng ngoài 8 fold phủ tới 06/2026. Thêm directional accuracy bỏ tiền gửi.

## Kiểm định
- Bootstrap khối vòng (khối 3 tháng) thay cho bootstrap iid; thêm tiêu chí mục 4.3 (|ΔSharpe| ≥ 0,1 và có ý nghĩa).
- Phân tích độ nhạy sàn biến động tiền gửi 2%/5%/8% (`16_sensitivity_analysis.py`, hiển thị trong app).

## App
- Tư vấn dùng tỷ trọng **hiện tại** (dữ liệu tới 08/2026) thay cho trung bình lịch sử; ghi rõ cửa sổ/tần suất tái cân bằng; nhãn khung thời gian khớp câu hỏi (<1 năm, 1–5 năm, >5 năm).
- Biểu đồ lợi nhuận tích lũy có đường gửi tiết kiệm; 7 phương pháp; nhãn tiếng Việt; bảng độ nhạy.

## Kết quả sau đợt 2 (Cân bằng / Trung hạn, 07/2023–08/2026)
Sharpe vượt trội: Markowitz 1,12 · MLP_MVO 1,06 · EW 0,72 · Risk Parity 0,71 · BL 0,66 · RL 0,53 · HRP 0,52. Mọi phương pháp vượt gửi tiết kiệm ở giai đoạn này (khác hẳn giai đoạn 2022–2024 của bản cũ). Holm-Bonferroni: 0/27 có ý nghĩa; bootstrap khối (không hiệu chỉnh): 6/27. H3: danh mục 6 tài sản có Sharpe cao hơn cổ phiếu–trái phiếu ở cả 5 phương pháp (+0,38 đến +0,78) nhưng chưa có ý nghĩa sau Holm.

# Đợt 3 — bỏ tháng chưa trọn 08/2026 (14/10/2026)

- `03_merge_panel.py`: `PANEL_END` 2026-08-01 → 2026-07-01. Giá cổ phiếu chỉ tới 17/08, trái phiếu tới 21/08 nên return "tháng 8" thực chất là nửa tháng, không so được với các tháng khác. Không bổ sung được vì vnstock đã bị gỡ khỏi PyPI (09/2026). Chạy lại `--stage all`.
- Giai đoạn kiểm tra: 07/2023–07/2026 (37 tháng, trước là 38). Tỷ trọng hiện tại = quyết định đầu 08/2026 dựa trên dữ liệu tới hết 07/2026.
- Sharpe vượt trội (Cân bằng / Trung hạn): Markowitz 1,09 · MLP_MVO 1,07 · RP 0,72 · EW 0,71 · BL 0,65 · HRP 0,53 · RL 0,52. Thứ hạng gần như giữ nguyên (MLP_MVO sát Markowitz hơn).
- Kiểm định: Holm-Bonferroni 0/27; bootstrap khối (không hiệu chỉnh) 6/27; H3: 6 tài sản vẫn hơn 2 tài sản ở cả 5 phương pháp (+0,37 đến +0,73), chưa có ý nghĩa sau Holm. Kết luận luận văn không đổi.

---

# Đợt 4 — sửa theo biên bản QC (24/10/2026)

Toàn bộ pipeline (03 → 19 và app) đã được viết lại phần mô hình và chạy lại từ dữ liệu thô. `scripts/19_qc_checks.py`
đối chiếu từng mục QC với kết quả và ghi `data/processed/qc_checks.csv` ([OK] / [FLAG] = còn thiếu dữ liệu / [INFO]).
`qc_audit.py` của người QC không có trong gói nhận được — cần chạy lại script đó để xác nhận độc lập.

## Kết luận mới phải viết trong Chương 4
1. Giai đoạn kiểm tra 09/2022–07/2026 (47 tháng) nay gồm cú sập cuối 2022, nên Sharpe vượt trội của mọi phương pháp
   giảm mạnh (0,16–0,36 cho 5 phương pháp chính và RL ở Cân bằng/Trung hạn; MLP_MVO 0,74). Nếu tính trên đúng cửa sổ cũ
   07/2023–07/2026, số mới gần bằng số cũ (Markowitz 1,17 so với 1,09; EW 0,74 so với 0,71). Phần lớn chênh lệch là do
   **giai đoạn**, không phải do phương pháp.
2. **Không đủ độ mạnh để phân biệt**: 0/11 cặp thuộc H1–H3 có ý nghĩa sau Holm. Ngưỡng phát hiện (α = 0,10, power 80%)
   là 0,20–1,19 đơn vị Sharpe; để phát hiện chênh lệch 0,3 cần 21–741 tháng tùy cặp. Không viết "không khác biệt".
3. **Vàng là yếu tố chi phối**: vàng đóng góp 94% lợi nhuận của Markowitz (giữ trung bình 50% vàng = trần) và 44–56%
   của EW/RP/HRP. H3 thực chất là "có vàng hay không": thêm vàng vào cổ phiếu–trái phiếu nâng Sharpe từ ~0,1 lên
   0,36–0,83; thêm cổ phiếu BĐS hoặc tiền mặt thì không (`h3_add_one_class.csv`).
4. **ML có kỹ năng nhỏ, không đồng đều**: R²_OS ElasticNet +4,4% gộp (Clark–West p = 0,03), dương ở cổ phiếu (+2,9%),
   cổ phiếu BĐS (+6,9%), trái phiếu (+10,5% — nhiều khả năng do chuỗi tổng hợp bị trơn), âm ở vàng (−5,0%). LightGBM
   +0,5%, MLP −0,1%. BL chỉ nhận view cổ phiếu/cổ phiếu BĐS (vàng không có kỹ năng, trái phiếu bị loại có chủ đích).
   BL (0,33) không khác Markowitz (0,36) có ý nghĩa (p = 0,94).
5. MLP_MVO có Sharpe cao nhất (0,74) nhưng MLP không có kỹ năng (R²_OS −0,1%, vàng −10%); lợi thế đến từ một lần
   chuyển sang 50% vàng cuối 2023, ngay trước đợt tăng của vàng. Deflated Sharpe 0,71 (N = 63) → không phải bằng chứng
   kỹ năng. Đây là ví dụ minh họa cho QC 16.
6. Dải khẩu vị vẫn quyết định nhiều: RP/HRP/EW ở sàn 40% trong 100% số lần tái cân bằng (Cân bằng) — thiết kế hai tầng,
   đã ghi rõ. Bỏ dải thì RP Cân bằng có Sharpe 0,46 (chỉ ~20% nhóm rủi ro); dải làm giảm 0,18. Với MVO/BL, dải là
   ràng buộc và chỉ chạm sàn ở 25–31% số lần.
7. Mô phỏng stationary bootstrap 1.000 lịch sử: khoảng 90% của Sharpe ngoài mẫu mỗi phương pháp rộng ~2,2 đơn vị;
   P(Markowitz > EW) = 0,75, P(BL > Markowitz) = 0,41, P(RP > EW) = 0,27, P(HRP > EW) = 0,16. Lưu ý: bootstrap lấy mẫu
   lại CHÍNH 78 tháng (vàng tăng mạnh) nên không tạo ra giai đoạn thị trường mới.
8. Thứ hạng giữa 9 kịch bản ổn định hơn nhiều (Spearman trung bình 0,72, trước 0,16) vì khung thời gian không còn đổi
   cửa sổ ước lượng.

## Bảng đối chiếu 23 mục QC

| # | Mức | Đã làm | File chính | Trạng thái |
|---|---|---|---|---|
| 1 | Chặn | Panel kéo về 02/2020 (78 tháng, có COVID 03/2020); test 47 tháng (trước 37) có cú sập 2022. Code sẵn sàng nhận chuỗi dài hơn | 03, `docs/data_request_qc.md` | **Một phần** — cần dữ liệu 2014–2019 để đạt ≥ 120 tháng |
| 2 | Chặn | SJC = vàng thế giới (World Bank) × 1,20565 × basis; basis nội suy log-tuyến tính giữa các neo thật, gắn cờ `reconstructed_*`. Kiểm chứng trên 47 tháng có giá thật: tương quan return 0,72 (nội suy giá: 0,59), vol 15,0% vs thật 18,6%. Vàng tại quyết định đầu: 31 quan sát, vol ước lượng 10,9% (trước 2,0%). Không quyết định nào dùng neo tương lai (test bắt đầu khi có giá thật tháng). Độ nhạy tắt phần dựng lại | 03, `gold_reconstruction_validation.csv`, 16 | **Xong**, trừ tách tỷ giá (cần `usd_vnd_monthly.csv`; hiện basis gộp tỷ giá + chênh lệch SJC) |
| 3 | Nặng | Gộp 1 lớp cổ phiếu, thực hiện qua E1VFVN30 (đề cương ghi ETF là "tùy chọn"); VN-Index chỉ là tham chiếu. Bản 6 lớp ở độ nhạy | common.UNIVERSES, 16 | Xong |
| 4 | Nặng | Đổi tên "cổ phiếu BĐS" (pipeline + app) | common, app | **Một phần** — rổ vẫn 4 mã chọn sau; cần chỉ số ngành/quy tắc chọn theo thời điểm |
| 5 | Nặng | Return tiền gửi tháng t dùng lãi suất cuối tháng t−1 (khớp carry trái phiếu). Tiền mặt hưởng lãi kỳ hạn khớp tần suất tái cân bằng (12T − 2,5 / 2,2 / 0 điểm %). Độ nhạy rf +0,5 / +1,0 điểm % và tắt chênh lệch kỳ hạn | 03, common, 16 | **Một phần** — chênh lệch kỳ hạn là giả định; cần trích dẫn nguồn lãi suất |
| 6 | Nặng | Đo giá đứng (54% ngày O=H=L=C, AC1 tháng 0,34); khử độ trơn Geltner khi ước lượng rủi ro (vol 4,5% → 6,4%); không lấy view ML cho trái phiếu; hook `bond_fund_nav.csv` | 03, 09, `data_quality_report.csv` | **Một phần** — cần NAV quỹ trái phiếu mở |
| 7 | Nặng | Winsorize ±3, tối thiểu 12 quan sát; momentum mọi lớp từ chỉ số tổng lợi nhuận (trái phiếu đúng dấu); tiền gửi bỏ khỏi ML | 03, 04 | Xong |
| 8 | Chặn | MVO/BL/MLP_MVO: dải là ràng buộc cvxpy. EW/RP/HRP: hai tầng (vol mục tiêu 5/10/16% + dải). Phân rã dải / chia trong nhóm / chia nhóm / đóng góp vàng | 09, engine, 18 | Xong |
| 9 | Chặn | Tiền gửi = tiền mặt nhận phần dư; MVO/BL tối ưu trên lợi nhuận vượt trội của lớp phi tiền mặt; RP/HRP trên lớp phi tiền mặt rồi co về vol mục tiêu; bỏ sàn vol | 09, engine | Xong |
| 10 | Nặng | Một bộ ước lượng cho mọi khung: EWMA HL 18 + Ledoit–Wolf (co tương quan). Khung thời gian = tần suất tái cân bằng + kỳ hạn tiền mặt. Cửa sổ 24/36 và HL 12/24 ở độ nhạy | 09, engine, 16 | Xong |
| 11 | Nặng | cvxpy + Clarabel (tất định), μ Bayes–Stein (Jorion 1986), phạt turnover theo phí lớp; 2 lần giải giống hệt | 09 | Xong (Markowitz vẫn là cược vàng — ghi trong kết luận) |
| 12 | Chặn | Bỏ view tiền gửi; δ = 2,5 cố định (độ nhạy 1,5/4); view chỉ khi R²_OS > 0 ngoài mẫu, mức tin cậy = λ* kiểu Idzorek; không có kỹ năng → BL = EW (test). Lần có >1 view giống nhau: 0% (trước 36/57) | 10, engine | Xong (view tương đối chưa làm — "cân nhắc") |
| 13 | Nặng | RL = contextual bandit chọn vị trí trong dải (sàn/giữa/trần); chỉ ở phụ lục, họ H4 riêng | 08 | Xong |
| 14 | Chặn | Dự báo ngoài mẫu point-in-time dùng chung cho đánh giá và backtest; target chia vol, trung bình lớp ngoài mô hình; ENet đường alpha đầy đủ; LGBM lưới nông + early stopping theo thời gian + 1-SE, dùng đúng cấu hình trong backtest; MLP dừng sớm theo thời gian, 5 seed; cửa sổ mở rộng; purge 1 tháng; 3 biến kinh tế (term spread, Δ lãi suất, basis SJC) có dấu định trước; R²_OS, Clark–West, rank IC | 05, 06, 07 | Xong (P/E, liên ngân hàng, USD/VND, khối ngoại: chưa có dữ liệu) |
| 15 | Chặn | Ngưỡng phát hiện, KTC 90%, số tháng cần; cột `conclusion` | 12 | Xong |
| 16 | Nặng | Holm theo họ H1/H2/H3 (không còn cặp "Khác"); Ledoit–Wolf 2008; Deflated Sharpe (N = 63 và 252). Kiểm tra Monte Carlo (`20_test_size_check.py`, T = 47, cùng Sharpe, tương quan 0,8): kích thước thực ~11–15% ở α = 10% với LW2008, ~18% với JK–Memmel → p-value hơi lạc quan, nên kết luận "không cặp nào có ý nghĩa" càng chắc | 12, 20 | Xong |
| 17 | Nặng | Stationary bootstrap 1.000 lịch sử; H3 thêm từng lớp | 17, 14 | Xong |
| 18 | Nhẹ | Vector phí theo lớp; độ nhạy phí đồng nhất 0,15% | common, 16 | Xong |
| 19 | — | Solver QP tất định, seed, 1 luồng BLAS, định dạng số cố định, `expected_checksums.json` + `99_verify_reproducibility.py` | run.py, 99 | Xong |
| 20 | — | Bỏ `filterwarnings("ignore")`; cảnh báo hội tụ ENet được đếm và ghi log | toàn bộ | Xong |
| 21 | — | 27 test: BL không view = prior và = EW; RP đóng góp rủi ro bằng nhau; HRP khớp bản tham chiếu López de Prado; MVO thỏa dải/trần; look-ahead tự động (xáo dữ liệu sau d); feature point-in-time | tests/ | Xong |
| 22 | — | Max drawdown tính cả điểm vốn 1,0 | common | Xong |
| 23 | — | Backend đọc `PVN_ADVISOR_METHOD` (mặc định RiskParity); app tĩnh, frontend, README, TODO cập nhật | backend, frontend | Xong |

## Số liệu trước / sau (Cân bằng / Trung hạn, Sharpe vượt trội)

| Phương pháp | Bản cũ 07/2023–07/2026 | Bản mới, cùng cửa sổ | **Bản mới 09/2022–07/2026** | Lợi nhuận/năm mới | Max DD mới |
|---|---|---|---|---|---|
| Markowitz | 1,09 | 1,17 | **0,36** | 10,2% | −24,4% |
| Black–Litterman (ENet) | 0,65 | 0,47 | **0,33** | 9,6% | −14,5% |
| Risk Parity | 0,72 | 0,81 | **0,28** | 8,3% | −16,5% |
| Equal Weight | 0,71 | 0,74 | **0,25** | 8,0% | −16,5% |
| HRP | 0,53 | 0,70 | **0,18** | 7,0% | −15,5% |
| MLP_MVO (mở rộng) | 1,07 | 1,01 | **0,74** | 17,9% | −15,5% |
| RL (phụ lục) | 0,52 | 0,62 | **0,16** | 7,0% | −21,7% |
| Tiền gửi 12T cùng kỳ | 5,1%/năm | | 5,5%/năm | | |

Đề xuất app (Risk Parity, Cân bằng/Trung hạn, dữ liệu tới 07/2026): cổ phiếu ETF 24,3% · cổ phiếu BĐS 15,7% · vàng 12,7% ·
trái phiếu 47,3% · tiền mặt 0% (bản cũ HRP: 51,9% trái phiếu, 7,8% tiền gửi, 0,3% vàng).

## Lệch so với đề cương — cần nêu và giải thích trong luận văn
- 6.1 / 4.2 (H3): bản chính 5 lớp (ETF là lớp cổ phiếu, VN-Index tham chiếu); bản 6 lớp ở độ nhạy.
- 6.4.3: δ cố định 2,5 thay cho δ từ Sharpe EW; Ω từ kỹ năng ngoài mẫu (λ*) thay cho EWMA bình phương sai số; không
  view cho tiền gửi và trái phiếu tổng hợp.
- 6.4.4: purge 1 tháng (nhãn 1 tháng), không embargo; dự báo dùng cửa sổ mở rộng.
- 6.5: khung thời gian chỉ đổi tần suất tái cân bằng và kỳ hạn tiền mặt; độ dài cửa sổ chuyển sang phân tích độ nhạy.
- 6.7: kiểm định chính Ledoit–Wolf 2008 (JK–Memmel để đối chiếu); Holm theo họ giả thuyết.
- 6.8: phí theo lớp thay cho 0,15% đồng nhất (0,15% ở độ nhạy).

## Kiểm tra lại
    python run.py --stage all --no-open
    python -m pytest tests
    python scripts/99_verify_reproducibility.py
    python scripts/19_qc_checks.py      # + qc_audit.py của người QC
Lần chạy sạch từ dữ liệu thô (24/10/2026, ~10 phút, 2 nhân) cho kết quả trùng từng byte với lần chạy trước
ở 34/35 file (file khác duy nhất là qc_checks.csv vì app được sửa giữa hai lần chạy).


## Đợt 4b — chuẩn bị đóng 5 cờ dữ liệu (24/10/2026)
Không đổi kết quả hiện tại (9/9 checksum khớp). Thêm các nhánh tự bật khi có dữ liệu (chi tiết và nguồn tải:
`docs/data_request_qc.md`):
- `03`: `PANEL_START` tự xác định từ dữ liệu thô; mã niêm yết muộn được giữ liên tục (cờ `not_listed`); rổ cổ phiếu BĐS
  `RE_BASKET` từ chỉ số ngành hoặc bảng thành viên theo năm (QC 4); cột `rate_1m`, `rate_3m` (QC 5); chuỗi vàng
  point-in-time `GOLD_SJC_RT` (QC 1–2).
- Engine tách return dùng để ƯỚC LƯỢNG (`R_est`, vàng point-in-time) khỏi return THỰC HIỆN (`R`); tiền mặt dùng lãi kỳ
  hạn thực khi có. `06` huấn luyện trên chuỗi ước lượng.
- Script mới: `00_check_raw_data.py`, `00_collect_stock_data.py` (tải theo năm từ 2014 + ứng viên rổ BĐS + VNREAL),
  `01c_collect_fmarket_nav.py`, `02b_build_raw_from_pricedancing.py`, `02c_convert_investing_csv.py`; `settings.json`;
  `data/raw/SOURCES.md`; backend chấp nhận 2 mã phụ.
- Test mới `tests/test_gold_vintage.py`. Chạy thử toàn bộ pipeline với dữ liệu GIẢ LẬP đúng định dạng 2014–2026:
  panel 141 tháng, kiểm tra 117 tháng, `19_qc_checks.py` không còn cờ dữ liệu; backend nhận kết quả.

## Đợt 4c — đóng cờ 5b: lãi suất kỳ hạn 1/3 tháng Vietcombank (24/10/2026)
- Chuỗi 12 tháng (pricedancing btQhHe) xác định là **Vietcombank, tại quầy, KHCN**: 44/48 tháng giá thật khớp tuyệt
  đối với bảng mốc VCB, 4 tháng lệch 0,1–0,2 điểm (ngày hiệu lực giữa tháng). Trích dẫn đã điền trong `SOURCES.md`.
- `data/raw/vcb_deposit_rate_events.csv`: 53 mốc 03/2014–08/2026, mỗi mốc có URL bài báo và `date_basis`;
  `scripts/02d_build_vcb_term_rates.py` → `deposit_rate_1m_3m.csv` (06/2014–07/2026). Khoảng chưa xác minh ghi
  `vcb_step_unverified_gap`: 01–08/2016, 10–12/2018, 11/2022–01/2023, 07/2023.
- `02b` không còn ghi đè file này: nếu có JSON pricedancing kỳ hạn 1/3 tháng thì chỉ thay các tháng đó.
- Tác động: phần tiền mặt khung ngắn/trung hạn hưởng lãi kỳ hạn thật thay giả định chênh 2,5/2,2 điểm. Lợi nhuận năm
  hóa đổi trung bình −0,06/−0,03 điểm % (ngắn/trung hạn; lớn nhất ±0,5 điểm), Sharpe đổi ≤ 0,03; khung dài hạn
  không đổi. Phương pháp Sharpe cao nhất ở cả 9 ô khẩu vị × khung thời gian không đổi.
- `19_qc_checks.py`: 23 OK, 4 FLAG (1, 2c, 4, 6), 8 INFO. Checksum cập nhật (9/9).

## Đợt 4e — đóng cờ 2c, lấp khoảng lãi suất, kéo dài lãi 12T về 2014 (24/10/2026)
- **2c USD/VND**: `scripts/01d_collect_imf_usdvnd.py` → `usd_vnd_monthly.csv` 01/2010–07/2026 từ IMF IFS (bản chép
  GitHub codeforIATI), bình quân tháng = (VND/SDR)/(USD/SDR). Đây là tỷ giá chính thức NHNN, không phải giá bán NHTM:
  phần chênh lệch thị trường–trung tâm nằm trong chênh lệch SJC của basis vàng.
- **Lãi kỳ hạn VCB**: lấp 3/4 khoảng trống (10–12/2018, 10/2022–03/2023, 06–07/2023) bằng ảnh chụp tháng của
  vietnambiz; mốc 05–06/2023 sửa theo vietnambiz (4,1/4,6 → 3,4/4,1). Còn 01–08/2016 chưa xác minh.
- **Lãi 12T 2014–06/2020**: `02d` bổ sung 76 tháng Vietcombank trước điểm pricedancing đầu tiên (`vcb_news_step`;
  01/2015–08/2016 `vcb_news_step_unverified`). Tiền gửi không còn chặn mốc panel (còn trái phiếu, vàng).
- **Tác động**: phương pháp Sharpe cao nhất ở 9 ô không đổi. Black–Litterman giảm trung bình 3,5 điểm %/năm (thấp
  nhất −6,0), MLP_MVO −0,15; các phương pháp khác ≈ 0. Nguyên nhân (kiểm tra bằng cách bỏ từng thay đổi): KHÔNG phải
  tỷ giá (bỏ tỷ giá, R²_OS ENet gần như không đổi) mà do 6 tháng đầu 2020 của lãi 12T: trước đây là giả định lùi
  phẳng 6,0%, nay là số thật của VCB (6,8% → 6,1%), làm đổi `term_spread` và `d_rate_3m` lúc đầu mẫu. R²_OS ENet giai
  đoạn kiểm tra: cổ phiếu BĐS 12,6% → 3,4%, ETF 5,0% → 0,8%; trái phiếu ~7% không đổi. Kết luận cho luận văn: kỹ năng
  dự báo cổ phiếu của ENet nhạy với vài quan sát macro đầu mẫu → không vững; BL lấy view từ các dự báo này nên giảm
  theo (Sharpe BL nay −0,11/−0,04/0,02 cho dài/ngắn/trung hạn, dưới EqualWeight).
- 28 test qua; `19_qc_checks.py`: 24 OK, 3 FLAG (1, 4, 6), 8 INFO; checksum cập nhật 9/9.

## Đợt 5 — đóng toàn bộ cờ dữ liệu: panel 02/2016–07/2026 (24/10/2026)
Thu thập qua Chrome của người dùng (Claude in Chrome), lưu số nguyên văn vào data/raw (nguồn: SOURCES.md).
- **Giá cổ phiếu** (Vietcap/VCI): giá cuối tháng 01/2014–07/2018 ghép vào file ngày; 96 tháng trùng có tỷ lệ cố định/mã
  → return trùng khớp. E1VFVN30 trên VCI chỉ có từ 01/2016 → ETF quyết định mốc panel. Bỏ VHM trước 05/2018 (mã cũ
  của doanh nghiệp khác). Thêm 20 mã ứng viên rổ BĐS + VIC/VRE/KBC.
- **TPCP 5 năm** (investing.com, khung Monthly) 01/2013–12/2019 ghép trước chuỗi ngày; 80 tháng trùng lệch ≤ 0,1 điểm.
- **Vàng SJC** (pricedancing, nến 6 tháng) 2009–2019; `02b`/`03` đọc nến 6 tháng (`real_6month_anchor`, dời 5 tháng);
  bật `gold_vintage = 1` → giai đoạn kiểm tra bắt đầu 02/2018.
- **Lãi Vietcombank 1/3 tháng** lấy thẳng từ pricedancing (chart TgKgHe, VjbhHe; trang lãi suất ghi rõ "Vietcombank")
  từ 07/2020, khớp bảng mốc báo chí (lệch ≤ 0,2 điểm); `02d` giữ các tháng pricedancing.
- **NAV quỹ trái phiếu** DCBF (Dragon Capital, Fmarket) 06/2013–10/2026; VFF để đối chiếu. Lưu ý tháng 07/2017
  (+5,7%) và 01/2018 (+4,6%) cần kiểm tra với báo cáo quỹ.
- **Rổ cổ phiếu BĐS point-in-time** `re_basket_membership.csv` 2015–2026 theo vốn hóa cuối năm N−1 (Vietcap IQ);
  cuối năm 2014–2017 là ước lượng (vốn hóa Q4/2018 × giá điều chỉnh tương đối) — bảng `re_basket_marketcap_ranking.csv`.
- **Kết quả**: panel 126 tháng, giai đoạn kiểm tra 102 tháng (02/2018–07/2026, gồm COVID 2020 và 2022).
  `19_qc_checks.py`: 27 OK, **0 FLAG**. Không giả thuyết nào bác bỏ sau Holm (H1–H3); ngưỡng phát hiện ΔSharpe 0,18–0,53.
  Sharpe cao nhất: dài hạn MLP_MVO (3/3 khẩu vị); ngắn hạn Black–Litterman (3/3); trung hạn BL/MLP_MVO/HRP.
  R²_OS ENet giai đoạn kiểm tra: BĐS 1,6%, ETF −5,4%, trái phiếu 9,9%, vàng 6,7% (CW p = 0,03).
- Test: pipeline 28/28 (test vàng point-in-time chọn neo gần nhất sau d, kể cả neo 6 tháng); backend 30/30 (cập nhật
  số ghim: 102 tháng; RiskParity cân bằng trung hạn 8,51% / vol 9,37% / MDD −22,04%). Checksum 9/9.

## Đợt 6 — cập nhật app theo mô hình mới (24/10/2026)
- **Trần 50%/lớp cho mọi phương pháp**: EW/RP/HRP áp trần sau phép chiếu dải (`09.cap_classes`; phần vượt của lớp
  phòng thủ → tiền gửi, của lớp rủi ro → lớp rủi ro còn chỗ, giữ tổng nhóm rủi ro). Lý do: NAV quỹ trái phiếu biến
  động thấp khiến RP Thận trọng dồn 85% vào trái phiếu. App (Risk Parity, trung hạn) nay: Thận trọng 6/4/5/50/35
  (ETF/BĐS/vàng/trái phiếu/tiền gửi), Cân bằng 24/16/3/50/7, Tăng trưởng 42/28/2/28/0.
  RP Cân bằng trung hạn: 8,46%/năm, vol 9,36%, Sharpe 0,28, MDD −22,0%.
- **Rổ BĐS trong app**: `03` ghi `re_basket_current.csv` (thành viên năm hiện hành + giá) → backend nạp như file tùy chọn;
  kế hoạch thực hiện mua VHM, NVL, KDH, VPI (2026); trang Thị trường/tin tự động dùng chuỗi `RE_BASKET`.
- **Nội dung**: nhãn trái phiếu = quỹ trái phiếu mở (NAV DCBF); nguồn dữ liệu từng lớp; ghi chú vàng (neo 6/4 tháng,
  tỷ giá IMF); trang Giới thiệu 102 tháng, 11 mã, 02/2016–07/2026; README/TODO.
- **Phiên bản**: V1 = `pipeline/data/processed` (đợt 6); `results/v2-delta4` chạy lại với δ = 4 trên cùng dữ liệu.
  Cơ sở dữ liệu demo cũ đã bỏ — app tự nạp lại khi khởi động; với bản đang chạy: Admin → Reset demo.
- Test: pipeline 29/29, backend 31/31 (thêm test rổ BĐS trong kế hoạch), frontend 9/9 + typecheck; QC 27 OK / 0 FLAG;
  checksum 9/9.

## Đợt 7 (25/10/2026)
- backend/app/domain/risk.py: cửa sổ lợi nhuận 12 tháng lăn trong báo cáo kế hoạch đọc chuỗi `HRP` (ghi cứng) trong khi tỷ trọng/chỉ số dùng `ADVISOR_METHOD` (Risk Parity) -> đổi sang `ADVISOR_METHOD`. Backend 31/31.

## Đợt 8 (26/10/2026)
- backend/app/domain/news.py: dòng nguồn của tin tự động còn ghi "HOSE (qua vnstock)" và "tệp dữ liệu lịch sử" -> cập nhật đúng nguồn hiện dùng: Vietcap (cổ phiếu, ETF, VN-Index), pricedancing.com và biểu lãi suất báo chí (vàng SJC, tiền gửi Vietcombank), Fmarket (NAV quỹ DCBF), Investing.com (lợi suất TPCP 5 năm); thêm bản tiếng Anh `SOURCE_LINE_EN`.
- Rà soát độ nhạy: biến thể `bond_views` trùng bản gốc vì R²_OS tích lũy của dự báo trái phiếu tại mọi thời điểm quyết định đều âm (−7,0% đến −1,8%) nên không có quan điểm nào được đưa vào; biến thể `cash_haircut` trùng vì lãi suất thực kỳ hạn 1/3 tháng có đủ mọi tháng nên chênh lệch giả định không được dùng. Không phải lỗi.
- Test: backend 31/31, pipeline 29/29, checksum 9/9.
