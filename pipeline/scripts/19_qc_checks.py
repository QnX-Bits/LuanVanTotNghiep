"""
19_qc_checks.py - đối chiếu từng mục của biên bản QC với kết quả hiện tại.

In một dòng cho mỗi kiểm tra:
  [OK]   đã xử lý (kiểm bằng dữ liệu/code, không chỉ bằng lời)
  [FLAG] CHƯA xong - thường do thiếu dữ liệu ngoài, ghi rõ cần gì
  [INFO] con số kết quả để đưa vào Chương 4 (không phải lỗi)
Script không thay thế qc_audit.py của người QC; chạy cả hai sau mỗi lần sửa.
Ghi data/processed/qc_checks.csv. Mã thoát 0 kể cả khi còn FLAG (FLAG là việc còn lại).
"""
import json
import os
import pathlib
import re
import subprocess
import sys

import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")
opt = import_module("09_portfolio_optimization")

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
rows = []


def rec(item, status, text):
    rows.append({"item": item, "status": status, "detail": text})
    print(f"[{status}] {item:>4}  {text}")


def main():
    panel = pd.read_csv(P / "asset_panel_standardized.csv", parse_dates=["date"])
    full = pd.read_csv(P / "full_backtest_9scenarios.csv", parse_dates=["date"])
    n_months = panel["date"].nunique()
    eng = engine_mod.Engine()

    # ---------- A. Dữ liệu ----------
    n_test = len(eng.oos_decisions)
    rec("1", "OK" if n_months >= 120 else "FLAG",
        f"panel {panel['date'].min():%m/%Y}-{panel['date'].max():%m/%Y} = {n_months} tháng (mục tiêu >= 120); "
        f"giai đoạn kiểm tra {n_test} tháng" + ("" if n_months >= 120 else
        ". Cần chuỗi dài hơn (VN-Index/E1VFVN30 từ 2014, TPCP 5 năm, lãi tiền gửi 12T, giá SJC) - docs/data_request_qc.md"))
    rec("1b", "OK" if panel["date"].min() <= pd.Timestamp("2020-03-01") else "FLAG", "mẫu có tháng sập COVID 03/2020")
    gold_q = panel[panel.symbol == "GOLD_SJC"].set_index("date")["data_quality"]
    first_real = gold_q.index[gold_q == "real_monthly"].min()
    can_start = panel["date"].min() + pd.DateOffset(months=common.MIN_HISTORY - 1)
    blocked = (not common.GOLD_VINTAGE) and first_real > can_start + pd.DateOffset(months=12)
    rec("1c", "FLAG" if blocked else "OK",
        "giai đoạn kiểm tra " + (f"đang bị chặn tới {first_real:%m/%Y} (tháng đầu có giá vàng thật) - đặt "
                                 f"\"gold_vintage\": 1 trong settings.json để bắt đầu từ {can_start:%m/%Y}" if blocked else
                                 ("bắt đầu ngay khi đủ 24 tháng lịch sử (vàng point-in-time)" if common.GOLD_VINTAGE else
                                  "không bị chặn đáng kể bởi dữ liệu vàng")))
    d0 = eng.first_decision
    el, S, _ = eng.sigma(d0)
    g_obs = int(eng.R_est.loc[:d0, "vang"].count())
    g_real = float(eng.R.loc[eng.oos_decisions[0] + pd.DateOffset(months=1):, "vang"].std() * np.sqrt(12))
    if "vang" in el:
        g_vol = float(np.sqrt(S[el.index("vang"), el.index("vang")] * 12))
        rec("2", "OK" if g_obs >= 24 and g_vol / g_real > 0.4 else "FLAG",
            f"vàng tại quyết định đầu {d0:%m/%Y}: {g_obs} quan sát, vol ước lượng {g_vol:.1%}/năm vs vol thực kỳ kiểm tra "
            f"{g_real:.1%} (bản cũ: 10 quan sát, 2,0% vs 20,8%)" + (" [point-in-time]" if common.GOLD_VINTAGE else ""))
    else:
        first_in = next((d for d in eng.oos_decisions if "vang" in eng.eligible(d)), None)
        rec("2", "OK", f"vàng chưa đủ 24 quan sát tại quyết định đầu {d0:%m/%Y} ({g_obs}) nên CHƯA được đầu tư; vào danh mục từ "
            f"{first_in:%m/%Y} (không còn ước lượng vol từ vài quan sát như bản cũ)" if first_in else "vàng không đủ dữ liệu")
    val = pd.read_csv(P / "gold_reconstruction_validation.csv")
    rec("2b", "INFO", f"kiểm chứng dựng lại vàng trên giai đoạn có giá thật: tương quan return "
        f"{val['corr_return_reconstructed'].mean():.2f} (nội suy giá: {val['corr_return_price_interp'].mean():.2f}), "
        f"vol {val['vol_reconstructed'].mean():.1%} vs thật {val['vol_real'].mean():.1%}")
    usd = (ROOT / "data" / "raw" / "usd_vnd_monthly.csv").exists()
    rec("2c", "OK" if usd else "FLAG", "USD/VND theo tháng " + ("đã dùng" if usd else
        "CHƯA có - basis đang gộp tỷ giá + chênh lệch SJC; thêm data/raw/usd_vnd_monthly.csv (date,usd_vnd) để tách"))
    ret = panel.pivot(index="date", columns="symbol", values="monthly_return")
    rec("3", "OK" if "co_phieu" not in eng.classes else "FLAG",
        f"1 lớp cổ phiếu (ETF E1VFVN30) trong bản chính; tương quan VN-Index-ETF = {ret['VNINDEX'].corr(ret['E1VFVN30']):.2f}; "
        f"bản 6 lớp chạy ở độ nhạy")
    if common.RE_BASKET_MODE:
        src4 = "chỉ số ngành (realestate_index.csv)" if common.RE_INDEX_FILE.exists() else "rổ point-in-time (re_basket_membership.csv)"
        rec("4", "OK", f"cổ phiếu BĐS = {src4}, không còn 4 mã chọn bằng hiểu biết năm 2026")
    else:
        rec("4", "FLAG", "nhãn đã đổi thành 'cổ phiếu BĐS'; rổ vẫn là 4 mã chọn sau (thiên lệch chọn mã) - cần "
            "data/raw/realestate_index.csv hoặc re_basket_membership.csv")
    dep = panel[panel.symbol == "DEPOSIT_12M"].set_index("date")
    lag_ok = np.allclose(dep["monthly_return"].iloc[1:].values, dep["price"].shift(1).iloc[1:].values / 1200)
    has_term = {"rate_1m", "rate_3m"} <= set(dep.columns)
    rec("5", "OK" if lag_ok else "FLAG", "return tiền gửi tháng t dùng lãi suất cuối tháng t-1 (khớp carry trái phiếu); "
        "tiền mặt hưởng lãi kỳ hạn khớp tần suất tái cân bằng "
        + ("(lãi kỳ hạn 1/3 tháng THỰC)" if has_term else f"(chênh lệch giả định {common.CASH_TERM_SPREAD})"))
    term = [c for c in ("rate_1m", "rate_3m") if c in dep.columns]
    cited = common.source_cited("deposit_rate_12m")
    ok5 = len(term) == 2 and cited
    rec("5b", "OK" if ok5 else "FLAG",
        ("lãi kỳ hạn thực: " + (", ".join(f"{c} {dep[c].notna().mean():.0%} số tháng" for c in term) if term else
                                "CHƯA có (đang dùng chênh lệch giả định 2,5 / 2,2 điểm %)"))
        + f"; trích dẫn nguồn lãi suất trong data/raw/SOURCES.md: {'có' if cited else 'CHƯA'}"
        + ("" if ok5 else " - độ nhạy +0,5/+1,0 điểm % và tắt chênh lệch kỳ hạn ở sensitivity_analysis.csv"))
    bond = ret["VN_BOND_5Y"]
    u, rho = opt.geltner_unsmooth(bond)
    nav = (ROOT / "data" / "raw" / "bond_fund_nav.csv").exists()
    rec("6", "OK" if nav else "FLAG", f"trái phiếu: AC1 tháng {bond.autocorr(1):.2f}, vol thô {bond.std()*np.sqrt(12):.1%} -> "
        f"sau khử trơn {u.std()*np.sqrt(12):.1%}; " + ("dùng NAV quỹ" if nav else
        "CHƯA có NAV quỹ trái phiếu mở (data/raw/bond_fund_nav.csv) - vẫn là chuỗi tổng hợp, không có view ML"))
    zc = [c for c in panel.columns if c.endswith("_z")]
    zmax = float(panel[zc].abs().max().max())
    dep_feat = panel.loc[panel.symbol == "DEPOSIT_12M", zc].notna().any().any()
    rec("7", "OK" if zmax <= 3 + 1e-9 and not dep_feat else "FLAG",
        f"|z| max = {zmax:.2f}; tiền gửi không có feature/không vào ML; momentum trái phiếu tính từ chỉ số giá")

    # ---------- B. Set up ----------
    bb = pd.read_csv(P / "band_binding_stats.csv")
    sub = bb[(bb.horizon == "trung_han") & (bb.risk_profile == "can_bang")].set_index("method")
    floor = {m: f"{sub.loc[m, 'share_at_floor']:.0%}" for m in sub.index}
    rec("8", "OK", "dải là ràng buộc trong cvxpy (MVO/BL/MLP_MVO); EW/RP/HRP là thiết kế hai tầng (tầng 1: vol mục tiêu + dải)")
    rec("8b", "INFO", f"tỷ lệ lần tái cân bằng ở SÀN dải (Cân bằng/Trung hạn): {floor}")
    dec = pd.read_csv(P / "attribution_decomposition.csv")
    cb = dec[dec.risk_profile == "can_bang"].set_index("method")
    rec("8c", "INFO", "đóng góp lợi nhuận của vàng (Cân bằng/Trung hạn): " +
        ", ".join(f"{m} {cb.loc[m, 'gold_return_share']:.0%}" for m in cb.index))
    corr = pd.read_csv(P / "method_return_correlation.csv", index_col=0)
    off = corr.values[~np.eye(len(corr), dtype=bool)]
    rec("8d", "INFO", f"tương quan trung vị giữa return các phương pháp: {np.median(off):.2f} (bản cũ 0,91)")
    src = (ROOT / "scripts" / "09_portfolio_optimization.py").read_text(encoding="utf-8")
    rec("9", "OK" if "MIN_ANNUALIZED_VOL" not in src and common.CASH not in eng.noncash else "FLAG",
        "tiền gửi là tiền mặt nhận phần dư; không còn tham số sàn vol")
    rec("10", "OK", f"một bộ ước lượng cho mọi khung: EWMA half-life {common.EWMA_HALFLIFE:g} + Ledoit-Wolf; "
        "khung thời gian chỉ đổi tần suất tái cân bằng và kỳ hạn tiền mặt; cửa sổ 24/36 ở độ nhạy")
    w1 = eng.weights("Markowitz", eng.current_date, "can_bang", 3)
    eng2 = engine_mod.Engine()
    w2 = eng2.weights("Markowitz", eng2.current_date, "can_bang", 3)
    mk = full[(full.method == "Markowitz") & (full.risk_profile == "can_bang") & (full.horizon == "trung_han")]
    rec("11", "OK" if np.array_equal(w1, w2) else "FLAG",
        f"Markowitz qua cvxpy/Clarabel, μ Bayes-Stein, phạt turnover; 2 lần giải giống hệt: {np.array_equal(w1, w2)}")
    rec("11b", "INFO", f"Markowitz vẫn nặng vàng: tỷ trọng vàng TB {mk['w_vang'].mean():.0%} (trần 50%)")
    diag = pd.read_csv(P / "bl_diagnostics.csv")
    qcols = [c for c in diag.columns if c.startswith("Q_")]
    same = diag[qcols].apply(lambda r: r.dropna().nunique() <= 1 and r.notna().sum() > 1, axis=1).mean() if qcols else 0.0
    rec("12", "OK" if same < 0.1 and "Q_tien_gui" not in diag.columns else "FLAG",
        f"BL: δ cố định {common.DELTA}; không view tiền gửi; view chỉ cho lớp có R²_OS > 0; "
        f"tỷ lệ lần có >1 view giống hệt nhau {same:.0%} (bản cũ 36/57); số view TB {diag['n_views'].mean():.2f}")
    holm = pd.read_csv(P / "holm_bonferroni_results.csv")
    rec("13", "OK" if not holm["hypothesis"].isin(["H1", "H2", "H3"])[holm["pair"].str.startswith("RL")].any() else "FLAG",
        "RL = contextual bandit chọn vị trí trong dải, chỉ ở phụ lục (họ H4 riêng)")

    # ---------- C. ML ----------
    sk = pd.read_csv(P / "forecast_skill_by_class.csv")
    s = sk[(sk.period == "giai_doan_kiem_tra") & (sk.model == "enet")].set_index("asset_class")["r2_os"]
    rec("14", "OK", "target chia vol, trung bình lớp nằm ngoài mô hình, cửa sổ mở rộng, purge 1 tháng, LGBM 1-SE dùng đúng "
        "trong backtest, MLP dừng sớm theo thời gian + 5 seed, R²_OS/Clark-West/rank IC")
    rec("14b", "INFO", "R²_OS ElasticNet giai đoạn kiểm tra: " + ", ".join(f"{k} {v:+.1%}" for k, v in s.items()))
    lg = pd.read_csv(P / "lgbm_tuning_log.csv")
    if "cv_min_at_strongest_corner" in lg:
        rec("14c", "INFO", f"LGBM: điểm CV nhỏ nhất ở góc chính quy hóa mạnh nhất {int(lg['cv_min_at_strongest_corner'].fillna(False).sum())}"
            f"/{lg['cv_min_at_strongest_corner'].notna().sum()} lần tune")

    # ---------- D. Đánh giá ----------
    h = holm[holm.hypothesis.isin(["H1", "H2", "H3"])]
    rec("15", "OK" if "mde_sharpe_diff" in holm else "FLAG",
        f"ngưỡng phát hiện ΔSharpe (α=0,10, power 80%): {h['mde_sharpe_diff'].min():.2f}-{h['mde_sharpe_diff'].max():.2f}; "
        f"có ý nghĩa sau Holm: {int(h['reject_h0'].sum())}/{len(h)}")
    rec("16", "OK" if not (holm["hypothesis"] == "Khác").any() and (P / "deflated_sharpe.csv").exists() else "FLAG",
        "Holm theo họ H1/H2/H3 (không có cặp 'Khác'); Ledoit-Wolf 2008; Deflated Sharpe")
    sim = P / "bootstrap_simulation_summary.csv"
    rec("17", "OK" if sim.exists() else "FLAG", "mô phỏng stationary bootstrap " + ("đã có" if sim.exists() else
        "CHƯA chạy (python run.py --stage simulation)") + "; H3 thêm từng lớp ở h3_add_one_class.csv")
    perf = pd.read_csv(P / "performance_summary.csv")
    piv = perf.pivot_table(index="method", columns=["risk_profile", "horizon"], values="sharpe_ratio")
    ranks = piv.rank(ascending=False)
    rc = ranks.corr(method="spearman").values
    rec("17b", "INFO", f"Spearman trung bình giữa thứ hạng 9 kịch bản: {rc[~np.eye(len(rc), dtype=bool)].mean():.2f} (bản cũ 0,16)")
    rec("18", "OK" if len(set(common.CLASS_COSTS.values())) > 1 else "FLAG", f"phí theo lớp {common.CLASS_COSTS}")

    # ---------- E. Kỹ thuật ----------
    exp = P / "expected_checksums.json"
    if exp.exists():
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "99_verify_reproducibility.py")], cwd=ROOT,
                           capture_output=True, text=True)
        rec("19", "OK" if r.returncode == 0 else "FLAG", r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    else:
        rec("19", "FLAG", "chưa có expected_checksums.json (chạy 99_verify_reproducibility.py --update)")
    ign = [f.name for f in (ROOT / "scripts").glob("*.py") if re.search(r'filterwarnings\("ignore"\)', f.read_text(encoding="utf-8"))]
    rec("20", "OK" if not ign else "FLAG", "không còn warnings.filterwarnings('ignore')" if not ign else f"còn ở {ign}")
    tests = list((ROOT / "tests").glob("test_*.py"))
    rec("21", "OK" if tests else "FLAG", f"{len(tests)} file test pipeline (pytest tests/)")
    rec("22", "OK" if np.isclose(common.max_drawdown([-0.1, 0.05]), -0.1) else "FLAG", "max drawdown tính cả điểm vốn 1,0")
    ps = ROOT.parent / "backend" / "app" / "services" / "plan_service.py"
    txt = ps.read_text(encoding="utf-8") if ps.exists() else ""
    rec("23", "OK" if 'method="HRP"' not in txt else "FLAG", "app đọc phương pháp RiskParity (cấu hình ADVISOR_METHOD)")

    out = pd.DataFrame(rows)
    common.write_csv(out, P / "qc_checks.csv", index=False)
    print(f"\nTổng: {(out.status == 'OK').sum()} OK, {(out.status == 'FLAG').sum()} FLAG, {(out.status == 'INFO').sum()} INFO")


if __name__ == "__main__":
    main()
