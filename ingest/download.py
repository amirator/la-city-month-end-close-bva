"""Download LA City Controller GL extracts (Socrata) for the analysed fiscal years; write a SHA-256 manifest."""
import datetime as dt, hashlib, json, pathlib, requests

DOMAIN = "https://controllerdata.lacity.org/resource"
SETS = {"expenditures_by_month": ("3ctd-sjrm", "fiscal_year"), "budget_and_expenditures": ("uyzw-yi8n", "budget_fiscal_year")}
YEARS = ["2024", "2025", "2026"]
RAW = pathlib.Path("data/raw")

def pull(ds, ycol):
    rows, off = [], 0
    where = f"{ycol} in ({','.join(repr(y) for y in YEARS)})".replace("'", "'")
    while True:
        r = requests.get(f"{DOMAIN}/{ds}.json", params={"$where": where, "$limit": 50000, "$offset": off, "$order": ":id"}, timeout=300)
        r.raise_for_status(); b = r.json(); rows += b; off += len(b)
        if len(b) < 50000: return rows

if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True); man = {}
    for name, (ds, ycol) in SETS.items():
        rows = pull(ds, ycol); p = RAW / f"{name}.json"
        p.write_text(json.dumps(rows, sort_keys=True))
        man[name] = {"dataset": ds, "url": f"https://controllerdata.lacity.org/d/{ds}", "rows": len(rows),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        print(name, len(rows))
    (RAW / "manifest.json").write_text(json.dumps(man, indent=2))
