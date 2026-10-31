import json, pathlib, sys
import duckdb, pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import os; os.chdir(ROOT)
import run

@pytest.fixture()
def con():
    c = duckdb.connect(); run.build(c, raw=ROOT / "tests/fixtures"); return c

def test_recon_classifies(con):
    r = dict(con.execute("select dept_code, status from recon_dept").fetchall())
    assert r == {"01": "ties", "02": "reconciling item"}       # 11*100-50 = 1050 ties; 1000110 vs 600 does not
    assert con.execute("select difference from recon_dept where dept_code='02'").fetchone()[0] == 1000110 - 600

def test_bva_and_overrun(con):
    row = con.execute("select adopted, revised, committed_amt, remaining, in_year_adjustments from bva_dept where dept_code='01'").fetchone()
    assert [float(x) for x in row] == [1000, 1200, 1050, 150, 200]
    assert con.execute("select dept_code, overrun from over_budget_accounts").fetchall() == [("02", 100)]

def test_close_checks(con):
    cc = {r[0]: r[1] for r in con.execute("select check_name, hits from close_checks").fetchall()}
    assert cc == {"negative_net_posting": 1, "spike_gt_5x_line_median": 0, "periods_missing": 0}  # line median 10 < 10k floor

def test_period_dim_maps_fiscal_to_calendar(con):
    d = dict(con.execute("select fiscal_month, month_start::varchar from dim_period").fetchall())
    assert d[1] == "2025-07-01" and d[6] == "2025-12-01" and d[7] == "2026-01-01" and d[12] == "2026-06-01"

def test_powerbi_exports_consistent():
    pb = ROOT / "powerbi"
    if not (pb / "fct_actual_monthly.csv").exists(): pytest.skip("exports absent")
    import pandas as pd
    f = pd.read_csv(pb / "fct_actual_monthly.csv", dtype=str); d = pd.read_csv(pb / "dim_department.csv", dtype=str)
    assert set(f.dept_code) <= set(d.dept_code)
    k = json.loads((ROOT / "reports/kpis.json").read_text())
    assert abs(f[f.fiscal_year == "2026"].amount.astype(float).sum() - k["monthly_postings"]) < 1
    for m in ["Utilisation %", "Ledger Difference", "Postings YTD"]:
        assert m in (pb / "measures.dax").read_text()

def test_readme_in_sync():
    import readme
    assert (ROOT / "README.md").read_text() == readme.render(json.loads((ROOT / "reports/kpis.json").read_text()))
