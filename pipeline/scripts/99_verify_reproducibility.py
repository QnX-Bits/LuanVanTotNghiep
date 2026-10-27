"""
99_verify_reproducibility.py - QC 19: kiểm tra kết quả TÁI LẬP được.

So SHA-256 của các file kết quả chính với data/processed/expected_checksums.json.
  python scripts/99_verify_reproducibility.py           # kiểm tra (mã thoát 1 nếu lệch)
  python scripts/99_verify_reproducibility.py --update  # ghi checksum kỳ vọng mới
Tái lập dựa trên: phiên bản ghim (requirements.txt), solver lồi tất định (Clarabel),
seed cố định, 1 luồng BLAS/OpenMP (run.py đặt OMP/MKL/OPENBLAS_NUM_THREADS=1), số ghi
với định dạng cố định (%.10g).
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
FILES = ["asset_panel_standardized.csv", "forecasts_oos.csv", "full_backtest_9scenarios.csv",
         "allocation_current.csv", "performance_summary.csv", "holm_bonferroni_results.csv",
         "bl_elasticnet_vs_lightgbm.csv", "h3_comparison_pairs.csv", "sensitivity_analysis.csv"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cur = {f: sha(P / f) for f in FILES if (P / f).exists()}
    exp_path = P / "expected_checksums.json"
    if "--update" in sys.argv:
        exp_path.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        print(f"Đã ghi {len(cur)} checksum vào {exp_path.name}")
        return 0
    exp = json.loads(exp_path.read_text(encoding="utf-8"))
    bad = [f for f in exp if cur.get(f) != exp[f]]
    for f in exp:
        print(f"{'OK  ' if f not in bad else 'LỆCH'} {f}")
    print(f"Tái lập: {len(exp) - len(bad)}/{len(exp)} file khớp checksum kỳ vọng")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
