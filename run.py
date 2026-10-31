"""Build star schema + month-end close pack for LA City FY2026 (Jul 2025 - Jun 2026)."""
import json, pathlib, sys
import duckdb, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

FY = 2026
RAW = pathlib.Path("data/raw")

def build(con, raw=RAW):
    con.execute(f"create or replace table raw_monthly as select * from read_json_auto('{raw}/expenditures_by_month.json', union_by_name=true)")
    con.execute(f"create or replace table raw_budget as select * from read_json_auto('{raw}/budget_and_expenditures.json', union_by_name=true)")
    con.execute(pathlib.Path("sql/01_model.sql").read_text())
    con.execute(f"set variable fy = {FY}")
    con.execute(pathlib.Path("sql/02_close.sql").read_text())

def kpis(con):
    one = lambda s: con.execute(s).fetchone()
    rec = {r[0]: {"lines": r[1], "difference": round(float(r[2]), 2)} for r in con.execute("select status, count(*), sum(difference) from recon_dept group by 1 order by 1").fetchall()}
    tot = one("select sum(monthly_postings), sum(budget_ledger_expenditures), sum(difference) from recon_dept")
    bva = one("select sum(adopted), sum(revised), sum(actual), sum(encumbered), sum(committed_amt), sum(remaining) from bva_dept")
    lo = con.execute("select department_name, round(utilisation,4), round(revised,0) from bva_dept where revised > 5e7 order by utilisation, dept_code limit 3").fetchall()
    top_adj = con.execute("select department_name, round(in_year_adjustments,0) from bva_dept order by in_year_adjustments desc, dept_code limit 3").fetchall()
    ob = one("select count(*), coalesce(sum(overrun),0) from over_budget_accounts")
    ob_top = con.execute("select department_name, account_name, round(overrun,0) from over_budget_accounts order by overrun desc, account_code limit 3").fetchall()
    cc = {r[0]: {"hits": r[1], "amount": None if r[2] is None else round(float(r[2]), 2)} for r in con.execute("select * from close_checks").fetchall()}
    ph = con.execute("select fiscal_month, strftime(month_start, '%Y-%m'), round(amount,2), round(share,4) from monthly_phasing order by 1").fetchall()
    rec_top = con.execute("select d.department_name, r.fund_code, round(difference,0) from recon_dept r join dim_department d using(dept_code) order by abs(difference) desc, r.dept_code, r.fund_code limit 3").fetchall()
    yoy = one("select sum(case when fiscal_year=2026 then amount end), sum(case when fiscal_year=2025 then amount end) from fct_actual_monthly")
    return {"fy": FY, "monthly_postings": round(float(tot[0]), 2), "budget_ledger_expenditures": round(float(tot[1]), 2),
            "net_difference": round(float(tot[2]), 2), "recon": rec, "recon_top": [[a, b, float(c)] for a, b, c in rec_top],
            "gf": {k: round(float(v), 2) for k, v in zip(["adopted", "revised", "actual", "encumbered", "committed", "remaining"], bva)},
            "gf_utilisation": round(float(bva[4] / bva[1]), 4),
            "gf_low_utilisation": [[a, float(b), float(c)] for a, b, c in lo], "gf_top_adjustments": [[a, float(b)] for a, b in top_adj],
            "gf_over_budget_accounts": int(ob[0]), "gf_overrun_total": round(float(ob[1]), 2),
            "gf_over_budget_top": [[a, b, float(c)] for a, b, c in ob_top], "close_checks": cc,
            "phasing": [[m, ms, float(a), float(s)] for m, ms, a, s in ph],
            "yoy_growth": round(float(yoy[0] / yoy[1] - 1), 4), "fy2025_postings": round(float(yoy[1]), 2)}

def export_powerbi(con):
    out = pathlib.Path("powerbi"); out.mkdir(exist_ok=True)
    for t, order in [("dim_department", "dept_code"), ("dim_fund", "fund_code"), ("dim_account", "account_code"), ("dim_period", "period_key")]:
        con.execute(f"copy (select * from {t} order by {order}) to '{out}/{t}.csv' (header)")
    con.execute(f"copy (select * from fct_actual_monthly where fiscal_year in (2025, 2026) order by all) to '{out}/fct_actual_monthly.csv' (header)")
    con.execute(f"copy (select * from fct_budget where fiscal_year in (2025, 2026) order by all) to '{out}/fct_budget.csv' (header)")

def close_pack(con):
    with pd.ExcelWriter("reports/close_pack_fy2026.xlsx") as xw:
        for t, sql in [("Recon", "select d.department_name, r.* from recon_dept r left join dim_department d using(dept_code) order by abs(difference) desc, dept_code, fund_code"),
                       ("BvA_GeneralFund", "select * from bva_dept order by revised desc"),
                       ("Overruns_GF", "select * from over_budget_accounts order by overrun desc"),
                       ("Close_checks", "select * from close_checks"), ("Phasing", "select * from monthly_phasing")]:
            con.execute(sql).df().to_excel(xw, sheet_name=t, index=False)

def charts(k, con):
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    ph = k["phasing"]
    ax[0].bar([p[1][2:] for p in ph], [p[2] / 1e9 for p in ph], color=["#c53030" if p[3] > 0.12 else "#2b6cb0" for p in ph])
    ax[0].axhline(sum(p[2] for p in ph) / 12 / 1e9, ls="--", color="gray", label="straight-line"); ax[0].legend()
    ax[0].set_title(f"FY{k['fy']} postings by month ($bn)"); ax[0].tick_params(axis="x", rotation=60)
    b = con.execute("select department_name, revised, committed_amt from bva_dept order by revised desc limit 8").fetchall()
    names = [n[:18] for n, _, _ in b][::-1]
    ax[1].barh(names, [float(r) / 1e9 for _, r, _ in b][::-1], color="#cbd5e0", label="revised budget")
    ax[1].barh(names, [float(c) / 1e9 for _, _, c in b][::-1], height=0.45, color="#2f855a", label="actual + encumbered")
    ax[1].set_title("General Fund: budget vs committed ($bn)"); ax[1].legend(fontsize=8)
    r = k["recon"]; labels = list(r)
    ax[2].bar(labels, [r[s]["lines"] for s in labels], color=["#2f855a" if s == "ties" else "#dd6b20" for s in labels])
    ax[2].set_title("Ledger tie-out: dept x fund lines"); ax[2].tick_params(axis="x", rotation=20)
    fig.tight_layout(); fig.savefig("reports/dashboard.png", dpi=110)

if __name__ == "__main__":
    con = duckdb.connect("data/close.duckdb"); build(con)
    k = kpis(con); pathlib.Path("reports").mkdir(exist_ok=True)
    pathlib.Path("reports/kpis.json").write_text(json.dumps(k, indent=2))
    export_powerbi(con); close_pack(con); charts(k, con)
    import readme; readme.write()
