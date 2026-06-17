-- SQL Server adaptation of q12.sql
-- using 1781290142 as a seed to the RNG

select
    l_shipmode,
    sum(case
        when o_orderpriority = '1-URGENT'
            or o_orderpriority = '2-HIGH'
            then 1
        else 0
    end) as high_line_count,
    sum(case
        when o_orderpriority <> '1-URGENT'
            and o_orderpriority <> '2-HIGH'
            then 1
        else 0
    end) as low_line_count
from
    orders,
    lineitem
where
    o_orderkey = l_orderkey
    and l_shipmode in ('RAIL', 'MAIL')
    and l_commitdate < l_receiptdate
    and l_shipdate < l_commitdate
    and l_receiptdate >= CAST('1995-01-01' AS date)
    and l_receiptdate < DATEADD(year, 1, CAST('1995-01-01' AS date))
group by
    l_shipmode
order by
    l_shipmode;
