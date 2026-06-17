-- SQL Server adaptation of q15.sql
-- using 1781290142 as a seed to the RNG

with revenue0 (supplier_no, total_revenue) as (
    select
        l_suppkey,
        sum(l_extendedprice * (1 - l_discount))
    from
        lineitem
    where
        l_shipdate >= CAST('1995-11-01' AS date)
        and l_shipdate < DATEADD(month, 3, CAST('1995-11-01' AS date))
    group by
        l_suppkey
)
select
    s_suppkey,
    s_name,
    s_address,
    s_phone,
    total_revenue
from
    supplier,
    revenue0
where
    s_suppkey = supplier_no
    and total_revenue = (
        select
            max(total_revenue)
        from
            revenue0
    )
order by
    s_suppkey;
