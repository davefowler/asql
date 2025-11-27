-- Source: dbt_zendesk
-- Model: int_zendesk__requester_updates
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_zendesk
-- File: models/intermediate/int_zendesk__requester_updates.sql

with ticket_updates as (
    select *
    from ticket_updates

), ticket as (
    select *
    from ticket

), ticket_requester as (
    select
        ticket.source_relation,
        ticket.ticket_id,
        ticket.requester_id,
        ticket_updates.valid_starting_at

    from ticket

    left join ticket_updates
        on ticket_updates.ticket_id = ticket.ticket_id
            and ticket_updates.user_id = ticket.requester_id
            and ticket_updates.source_relation = ticket.source_relation

), final as (
    select
        source_relation,
        ticket_id,
        requester_id,
        max(valid_starting_at) as last_updated,
        count(*) as total_updates
    from ticket_requester

    group by 1, 2, 3
)

select *
from final