select top (10)
    o_orderpriority,
    count(*) as order_count
from
    orders
where
    o_orderdate >= '1995-04-01'
    and o_orderdate < DATEADD(month, 3, '1995-04-01')
    and exists (
        select
            1
        from
            lineitem
        where
            l_orderkey = o_orderkey
            and l_commitdate < l_receiptdate
    )
group by
    o_orderpriority
order by
    o_orderpriority;