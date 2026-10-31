import json, pathlib

def render(k):
    bn = lambda x: f"${x/1e9:,.2f}bn"; mn = lambda x: ("-" if x < 0 else "") + f"${abs(x)/1e6:,.1f}m"; pct = lambda x: f"{x*100:.1f}%"
    g = k["gf"]; r = k["recon"]; cc = k["close_checks"]; ph = k["phasing"]
    june = ph[11]; july = ph[0]
    lines = sum(v["lines"] for v in r.values())
    rt = "; ".join(f"{a.title()} fund {f} ({mn(d)})" for a, f, d in k["recon_top"])
    low = "; ".join(f"{a.title()} {pct(u)} of {mn(b)}" for a, u, b in k["gf_low_utilisation"])
    adj = ", ".join(f"{a.title()} (+{mn(v)})" for a, v in k["gf_top_adjustments"])
    over = ("**No General Fund account was committed above its revised appropriation**. Appropriation control held at line level."
            if k["gf_over_budget_accounts"] == 0 else f"{k['gf_over_budget_accounts']} General Fund accounts were committed above budget ({mn(k['gf_overrun_total'])}).")
    return f"""# LA City month-end close & budget-vs-actual (FY{k['fy']})

A month-end close and budget-vs-actual pack built on the **City of Los Angeles Controller's real general-ledger extracts** for FY{k['fy']} (Jul {k['fy']-1} to Jun {k['fy']}). It includes a subledger-to-ledger tie-out, General Fund BvA, automated close checks, an Excel close pack and a Power BI-ready star schema with DAX measures.

![dashboard](reports/dashboard.png)

## Business problem
At every close, a finance team has to prove three things: that monthly postings tie to the budget ledger, where spend stands against the revised budget, and which postings need a second look before sign-off. This repo automates those three steps in SQL and produces a reviewable workpaper.

## Data
- **City Expenditures by Month**, LA City Controller, Socrata [`3ctd-sjrm`](https://controllerdata.lacity.org/d/3ctd-sjrm): monthly postings by department × fund × account.
- **City Budget and Expenditures**, LA City Controller, Socrata [`uyzw-yi8n`](https://controllerdata.lacity.org/d/uyzw-yi8n): adopted and revised budget, actuals and encumbrances by budget fiscal year.
- `python ingest/download.py` pulls both (FY2024 to FY2026 filter) and writes a SHA-256 manifest. Raw data is not committed.

## Method
1. `sql/01_model.sql`: staging with `TRY_CAST` to decimals, a star schema (`dim_department`, `dim_fund`, `dim_account`, `dim_period` mapping fiscal to calendar months) and two facts (`fct_actual_monthly`, `fct_budget`).
2. `sql/02_close.sql` (FY passed as a DuckDB variable):
   - **Tie-out**: monthly postings vs budget-ledger total expenditures by department × fund, classified as ties, reconciling item, or one-sided.
   - **General Fund BvA**: adopted → revised → actual + encumbrance, with remaining budget and utilisation.
   - **Over-committed accounts**: General Fund lines where committed spend exceeds revised budget.
   - **Close checks**: negative net postings (reversals/credits), spikes above 5x the line's median month (floor $10k) and missing periods.
   - **Phasing**: monthly share of spend vs a straight-line budget.
3. Outputs: `reports/close_pack_fy{k['fy']}.xlsx` (5 tabs), `powerbi/*.csv` (star schema for FY2025-26) and `powerbi/measures.dax` (YTD, PY, YoY, utilisation, straight-line phasing variance, ledger difference).

## Key findings (FY{k['fy']})
- **Tie-out**: monthly postings total {bn(k['monthly_postings'])} vs {bn(k['budget_ledger_expenditures'])} in the budget ledger, a net difference of **{mn(k['net_difference'])}**. **{r['ties']['lines']} of {lines}** department × fund lines tie to the cent. {r['reconciling item']['lines']} carry reconciling items, and {r['monthly postings only']['lines']} have postings with no budget line. The largest differences are {rt}. The likely cause is timing: the budget extract is keyed by *budget* fiscal year (spend against prior-year appropriations and encumbrances), while postings are keyed by *transaction* month. This is an inference from the dataset definitions, not confirmed by the Controller.
- **General Fund BvA**: the budget went from {bn(g['adopted'])} adopted to **{bn(g['revised'])} revised** (+{mn(g['revised']-g['adopted'])} in-year; the biggest moves were {adj}). Committed spend was **{bn(g['committed'])}** ({bn(g['actual'])} actual + {mn(g['encumbered'])} encumbered), or **{pct(k['gf_utilisation'])} utilisation**, leaving {mn(g['remaining'])} unspent.
- Lowest utilisation among departments with more than $50m budget: {low}.
- {over}
- **Phasing**: June (year-end) carried **{pct(june[3])}** of the year's postings and July {pct(july[3])}, against 8.3% straight-line. That is a year-end accrual and true-up pattern a monthly forecast must allow for.
- **Close checks**: {cc['negative_net_posting']['hits']} negative net postings (total {mn(cc['negative_net_posting']['amount'])}) and {cc['spike_gt_5x_line_median']['hits']} spikes above 5x the line median were flagged for review. {cc['periods_missing']['hits']} periods are missing.
- Total postings grew **{pct(k['yoy_growth'])}** from FY{k['fy']-1} ({bn(k['fy2025_postings'])}).

## Skills shown
GL/subledger reconciliation logic · budget vs actual and encumbrance accounting · month-end close checks · SQL (DuckDB: CTEs, window functions, full outer joins) · star-schema modelling for Power BI with DAX measures · Excel workpaper automation (pandas/openpyxl) · Python · pytest · GitHub Actions.

## How to run
```bash
pip install -r requirements.txt
python ingest/download.py && python run.py
python -m pytest -q        # unit tests run on a small hand-made fixture in tests/fixtures
```
To use the star schema in Power BI, load `powerbi/*.csv`, create the relationships listed at the top of `measures.dax`, then paste in the measures.

## Honest caveats
- **No Power BI file (.pbix) is included.** The DAX was written as text mirroring the SQL and has not been validated in Power BI Desktop.
- These are public extracts, not a live ERP. "Close" here means analytics over posted data, not journal entry or approval workflow.
- The explanation for the reconciling items is inferred from the dataset definitions.
- This is an independent portfolio project, not work for the City of Los Angeles.

MIT licence · Amir Khan
"""

def write():
    pathlib.Path("README.md").write_text(render(json.loads(pathlib.Path("reports/kpis.json").read_text())))
