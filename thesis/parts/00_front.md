# Khóa luận tốt nghiệp — Tối ưu hóa danh mục đa tài sản cho nhà đầu tư Việt Nam

2026-10-25 · 

## Trang bìa

**TRƯỜNG ĐẠI HỌC KINH TẾ THÀNH PHỐ HỒ CHÍ MINH (UEH)**

[Khoa / Trường thành viên — điền theo mẫu của khoa]

**KHÓA LUẬN TỐT NGHIỆP**

**TỐI ƯU HÓA DANH MỤC ĐA TÀI SẢN CHO NHÀ ĐẦU TƯ VIỆT NAM: SO SÁNH CÁC PHƯƠNG PHÁP PHÂN BỔ TRUYỀN THỐNG VÀ HỌC MÁY**

Chuyên ngành: Khoa học dữ liệu

Sinh viên thực hiện: [Họ và tên] — MSSV: 31231026504

Giảng viên hướng dẫn: TS. Nguyễn Đăng Cao

TP. Hồ Chí Minh, tháng 11 năm 2026

## Lời cam đoan

Tôi xin cam đoan khóa luận “Tối ưu hóa danh mục đa tài sản cho nhà đầu tư Việt Nam” là công trình nghiên cứu của tôi dưới sự hướng dẫn của TS. Nguyễn Đăng Cao. Các số liệu và kết quả trong khóa luận được tính toán từ dữ liệu công khai có trích nguồn và có thể tái lập bằng mã nguồn đính kèm. [Bổ sung câu khai báo việc sử dụng công cụ AI theo quy định của UEH.]

TP. Hồ Chí Minh, ngày … tháng … năm 2026 — Sinh viên ký tên

## Tóm tắt

Khóa luận so sánh bảy phương pháp phân bổ danh mục — phân bổ đều, Markowitz, Risk Parity, Hierarchical Risk Parity, Black–Litterman với quan điểm từ học máy, tối ưu với dự báo MLP và học tăng cường — trên danh mục 5 lớp tài sản mà nhà đầu tư cá nhân Việt Nam thực hiện được: cổ phiếu (ETF E1VFVN30), rổ cổ phiếu bất động sản, vàng SJC, quỹ trái phiếu mở và tiền gửi Vietcombank. Dữ liệu tháng 02/2016–07/2026 được dựng theo nguyên tắc point-in-time; backtest walk-forward 102 tháng trên 9 kịch bản khẩu vị × khung thời gian, có chi phí giao dịch theo lớp; chênh lệch Sharpe được kiểm định bằng phương pháp Ledoit–Wolf (2008) với hiệu chỉnh Holm. Kết quả: mô hình học máy không dự báo được cổ phiếu nhưng có kỹ năng với vàng; Black–Litterman có Sharpe cao nhất trong nhóm 5 phương pháp chính ở 8/9 kịch bản, nhưng không cặp so sánh nào có ý nghĩa thống kê và thứ hạng không vững qua mô phỏng bootstrap và phân tích độ nhạy. Khẩu vị rủi ro và đa dạng hóa sang vàng, trái phiếu quan trọng hơn lựa chọn thuật toán. Kết quả được đưa vào ứng dụng tư vấn PortfolioVN dùng Risk Parity, chuyển tỷ trọng thành kế hoạch mua cụ thể.

**Từ khóa:** phân bổ tài sản, Black–Litterman, Risk Parity, học máy, kiểm định Sharpe, Việt Nam.

## Abstract

This thesis compares seven allocation methods — equal weight, Markowitz, Risk Parity, Hierarchical Risk Parity, Black–Litterman with machine-learning views, mean–variance with MLP forecasts, and a reinforcement-learning bandit — on a five-asset portfolio available to Vietnamese retail investors: an equity ETF (E1VFVN30), a real-estate stock basket, SJC gold, an open-ended bond fund and Vietcombank deposits. Monthly data for 02/2016–07/2026 are built point-in-time; a 102-month walk-forward backtest covers nine risk-profile × horizon scenarios with class-specific transaction costs, and Sharpe differences are tested with Ledoit–Wolf (2008) and Holm corrections. Machine-learning models fail to forecast equities but show skill for gold; Black–Litterman achieves the highest Sharpe among the five main methods in 8 of 9 scenarios, yet no difference is statistically significant and the ranking is not robust to bootstrap simulation or sensitivity checks. Risk level and diversification into gold and bonds matter more than the choice of algorithm. The results are delivered through PortfolioVN, an advisory application based on Risk Parity.

**Keywords:** asset allocation, Black–Litterman, risk parity, machine learning, Sharpe ratio test, Vietnam.

## Mục lục

*Tạo tự động khi xuất sang Word (References → Table of Contents), dựa trên các tiêu đề chương và mục.*

## Danh mục từ viết tắt

| Viết tắt | Tiếng Anh | Tiếng Việt |
| --- | --- | --- |
| BĐS | – | Bất động sản |
| API | Application Programming Interface | Giao diện lập trình ứng dụng |
| BL | Black–Litterman | Mô hình Black–Litterman |
| CV | Cross-validation | Kiểm định chéo |
| CVaR | Conditional Value at Risk | Giá trị rủi ro có điều kiện |
| DSR | Deflated Sharpe Ratio | Hệ số Sharpe điều chỉnh thiên lệch chọn lọc |
| ERC | Equal Risk Contribution | Đóng góp rủi ro đều |
| ETF | Exchange-Traded Fund | Quỹ hoán đổi danh mục |
| EW | Equal Weight | Phân bổ đều |
| EWMA | Exponentially Weighted Moving Average | Trung bình trượt có trọng số mũ |
| HAC | Heteroskedasticity and Autocorrelation Consistent | Vững với phương sai thay đổi và tự tương quan |
| HOSE | Ho Chi Minh Stock Exchange | Sở Giao dịch Chứng khoán TP.HCM |
| HRP | Hierarchical Risk Parity | Phân bổ rủi ro cân bằng phân cấp |
| IC | Information Coefficient | Hệ số thông tin |
| LW | Ledoit–Wolf | – |
| MDD | Maximum Drawdown | Mức sụt giảm tối đa |
| MDE | Minimum Detectable Effect | Chênh lệch tối thiểu phát hiện được |
| MLP | Multilayer Perceptron | Mạng nơ-ron nhiều lớp |
| MVO | Mean–Variance Optimization | Tối ưu trung bình–phương sai |
| NAV | Net Asset Value | Giá trị tài sản ròng |
| RL | Reinforcement Learning | Học tăng cường |
| RP | Risk Parity | Phân bổ cân bằng rủi ro |
| R²_OS | Out-of-sample R² | R² ngoài mẫu |
| SJC | Saigon Jewelry Company | Công ty Vàng bạc Đá quý Sài Gòn |
| SR | Sharpe Ratio | Hệ số Sharpe |
| TPCP / TPDN | – | Trái phiếu Chính phủ / Trái phiếu doanh nghiệp |
| VaR | Value at Risk | Giá trị chịu rủi ro |
| VCB | Vietcombank | Ngân hàng TMCP Ngoại thương Việt Nam |

## Danh mục bảng và hình

*Tạo tự động khi xuất sang Word (Insert Table of Figures) từ các chú thích “Bảng x.y” và “Hình x.y”. Toàn bộ khóa luận có 30 bảng trong chương (1.1–1.2, 2.1–2.2, 3.1–3.9, 4.1–4.9, 5.1–5.4, 6.1), 4 hình dữ liệu (4.1–4.3, 5.1) và các ảnh chụp màn hình ứng dụng cần chèn (Hình 5.2–5.5, Phụ lục G).*
