-- Month-end close analytics for FY = getvariable('fy')
-- 1. Subledger (monthly postings) vs budget ledger tie-out by department and fund
create or replace table recon_dept as
with m as (select dept_code, fund_code, sum(amount) amt from fct_actual_monthly where fiscal_year = getvariable('fy') group by 1, 2),
     b as (select dept_code, fund_code, sum(total_expenditures) amt from fct_budget where fiscal_year = getvariable('fy') group by 1, 2)
select coalesce(m.dept_code, b.dept_code) dept_code, coalesce(m.fund_code, b.fund_code) fund_code,
       coalesce(m.amt, 0) monthly_postings, coalesce(b.amt, 0) budget_ledger_expenditures,
       coalesce(m.amt, 0) - coalesce(b.amt, 0) as difference,
       case when abs(coalesce(m.amt, 0) - coalesce(b.amt, 0)) < 1 then 'ties'
            when m.amt is null then 'budget ledger only' when b.amt is null then 'monthly postings only' else 'reconciling item' end as status
from m full join b using (dept_code, fund_code);

-- 2. Budget vs actual, General Fund, by department
create or replace table bva_dept as
select f.dept_code, d.department_name, sum(adopted_budget) adopted, sum(revised_budget) revised,
       sum(actual_expense) actual, sum(encumbrance) encumbered, sum(total_expenditures) committed_amt,
       sum(revised_budget) - sum(total_expenditures) as remaining,
       sum(total_expenditures) / nullif(sum(revised_budget), 0) as utilisation,
       sum(revised_budget) - sum(adopted_budget) as in_year_adjustments
from fct_budget f join dim_department d using (dept_code)
where fiscal_year = getvariable('fy') and fund_code = '100'
group by 1, 2;

-- 3. Over-committed_amt accounts (committed_amt > revised budget), all funds
create or replace table over_budget_accounts as
select f.dept_code, d.department_name, f.fund_code, f.account_code, a.account_name, revised_budget, total_expenditures,
       total_expenditures - revised_budget as overrun
from fct_budget f join dim_department d using (dept_code) join dim_account a using (account_code)
where fiscal_year = getvariable('fy') and fund_code = '100' and total_expenditures > revised_budget + 1;

-- 4. Close checks on monthly postings
create or replace table close_checks as
with series as (
  select dept_code, fund_code, account_code, fiscal_month, sum(amount) amt
  from fct_actual_monthly where fiscal_year = getvariable('fy') group by all),
stats as (
  select *, median(abs(amt)) over (partition by dept_code, fund_code, account_code) med,
         count(*) over (partition by dept_code, fund_code, account_code) n
  from series)
select 'negative_net_posting' as check_name, count(*) as hits, sum(amt) as amount from series where amt < 0
union all
select 'spike_gt_5x_line_median', count(*), sum(amt) from stats where n >= 6 and med > 10000 and abs(amt) > 5 * med
union all
select 'periods_missing', 12 - count(distinct fiscal_month), null from series;

-- 5. Monthly phasing vs straight-line, all funds
create or replace table monthly_phasing as
select p.fiscal_month, p.month_start, sum(amount) amount,
       sum(sum(amount)) over (order by p.fiscal_month) cumulative,
       sum(amount) / sum(sum(amount)) over () as share
from fct_actual_monthly f join dim_period p using (period_key)
where f.fiscal_year = getvariable('fy') group by 1, 2 order by 1;
