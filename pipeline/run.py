"""
Điểm vào duy nhất của đồ án.
  python run.py                     -> build app từ kết quả có sẵn rồi mở trình duyệt
  python run.py --stage backtest    -> 11,15,14,12,13,16,18,19 (backtest + kiểm định + độ nhạy + QC) rồi build app
  python run.py --stage forecasts   -> thêm 06, 07 (dự báo ML ngoài mẫu) trước backtest
  python run.py --stage all         -> 03, 04 (panel) + forecasts + backtest + 17 (mô phỏng bootstrap)
  python run.py --stage simulation  -> chỉ 17 (mô phỏng stationary bootstrap, ~10 phút)
Bước 00-02, 01b (thu thập dữ liệu) chạy tay vì cần mạng.
Tái lập: mọi bước chạy với 1 luồng BLAS/OpenMP (QC 19); kiểm tra bằng scripts/99_verify_reproducibility.py.
"""
import argparse
import os
import pathlib
import subprocess
import sys
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
BACKTEST = ["11_full_backtest_scenarios", "15_bl_lightgbm_comparison", "14_h3_diversification_test",
            "12_holm_bonferroni_comparison", "13_dashboard_summary_metrics", "16_sensitivity_analysis",
            "18_attribution_decomposition", "19_qc_checks"]
FORECASTS = ["06_train_models", "07_deep_learning_extension"]
DATA = ["03_merge_panel", "04_standardize_panel"]
STAGES = {"app": [], "backtest": BACKTEST, "forecasts": FORECASTS + BACKTEST,
          "all": DATA + FORECASTS + BACKTEST + ["17_bootstrap_simulation", "19_qc_checks"],
          "simulation": ["17_bootstrap_simulation", "19_qc_checks"]}
THREADS = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=list(STAGES), default="app")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    env = dict(os.environ, PYTHONPATH=str(SCRIPTS), PYTHONIOENCODING="utf-8", **THREADS)
    for s in STAGES[a.stage]:
        print(f"\n=== {s} ===", flush=True)
        if subprocess.run([sys.executable, str(SCRIPTS / f"{s}.py")], cwd=ROOT, env=env).returncode:
            sys.exit(f"Lỗi ở bước {s}. Dừng.")
    sys.path.insert(0, str(ROOT / "app"))
    import build_app
    out = build_app.main()
    if not a.no_open:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
