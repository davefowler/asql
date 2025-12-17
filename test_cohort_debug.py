from asql.preparse import preparse_asql

q = 'from events group by month(event_date) (count(distinct user_id) as active)'
print("Original:", q)
print("Preparsed:", preparse_asql(q))
