-- SQL Server adaptation of q6.sql
-- using 1781290141 as a seed to the RNG

select
    sum(l_extendedprice * l_discount) as revenue
from
    lineitem
where
    l_shipdate >= CAST('1993-01-01' AS date)
    and l_shipdate < DATEADD(year, 1, CAST('1993-01-01' AS date))
    and l_discount between 0.03 - 0.01 and 0.03 + 0.01
    and l_quantity < 25;
