-- Staging + star schema. Raw JSON loaded as raw_monthly / raw_budget by run.py.
create or replace table fct_actual_monthly as
select try_cast(fiscal_year as int) as fiscal_year, try_cast(fiscal_month_number as int) as fiscal_month,
       try_cast(fiscal_period as int) as period_key, department as dept_code, fund as fund_code, account as account_code,
       coalesce(account_group_name, 'UNCLASSIFIED') as account_group, try_cast(expenditures as decimal(18,2)) as amount
from raw_monthly;

create or replace table fct_budget as
select try_cast(budget_fiscal_year as int) as fiscal_year, department as dept_code, fund as fund_code, account as account_code,
       coalesce(account_group_name, 'UNCLASSIFIED') as account_group,
       try_cast(adopted_budget_amount as decimal(18,2)) as adopted_budget,
       try_cast(total_budget as decimal(18,2)) as revised_budget,
       try_cast(actual_expense as decimal(18,2)) as actual_expense,
       try_cast(encumbrance_amount as decimal(18,2)) as encumbrance,
       try_cast(total_expenditures as decimal(18,2)) as total_expenditures
from raw_budget;

create or replace table dim_department as
select dept_code, any_value(department_name order by fy desc) as department_name from (
  select department as dept_code, department_name, try_cast(fiscal_year as int) fy from raw_monthly
  union all select department, department_name, try_cast(budget_fiscal_year as int) from raw_budget) group by 1;
create or replace table dim_fund as
select fund_code, any_value(fund_name order by fy desc) as fund_name, fund_code = '100' as is_general_fund from (
  select fund as fund_code, fund_name, try_cast(fiscal_year as int) fy from raw_monthly
  union all select fund, fund_name, try_cast(budget_fiscal_year as int) from raw_budget) group by 1;
create or replace table dim_account as
select account_code, any_value(account_name order by fy desc) as account_name from (
  select account as account_code, account_name, try_cast(fiscal_year as int) fy from raw_monthly
  union all select account, account_name, try_cast(budget_fiscal_year as int) from raw_budget) group by 1;
create or replace table dim_period as
select distinct period_key, fiscal_year, fiscal_month,
       make_date(fiscal_year - case when fiscal_month <= 6 then 1 else 0 end, ((fiscal_month + 5) % 12) + 1, 1) as month_start
from fct_actual_monthly;
