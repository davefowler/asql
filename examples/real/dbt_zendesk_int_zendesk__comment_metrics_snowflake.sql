-- Source: dbt_zendesk
-- Model: int_zendesk__comment_metrics
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_zendesk
-- File: models/intermediate/int_zendesk__comment_metrics.sql

with ticket_comments as (

    select *
    from ticket_comments
),

comment_counts as (
    select
        source_relation,
        ticket_id,
        last_comment_added_at,
        sum(case when commenter_role = 'internal_comment' and is_public = true
            then 1
            else 0
                end) as count_public_agent_comments,
        sum(case when commenter_role = 'internal_comment'
            then 1
            else 0
                end) as count_agent_comments,
        sum(case when commenter_role = 'external_comment'
            then 1
            else 0
                end) as count_end_user_comments,
        sum(case when is_public = true
            then 1
            else 0
                end) as count_public_comments,
        sum(case when is_public = false
            then 1
            else 0
                end) as count_internal_comments,
        count(*) as total_comments,
        count(distinct case when commenter_role = 'internal_comment'
            then user_id
                end) as count_ticket_handoffs,
        sum(case when commenter_role = 'internal_comment' and is_public = true and previous_commenter_role != 'first_comment'
            then 1
            else 0
                end) as count_agent_replies
    from ticket_comments

    group by 1, 2, 3
),

final as (
    select
        *,
        count_public_agent_comments = 1 as is_one_touch_resolution,
        count_public_agent_comments = 2 as is_two_touch_resolution
    from comment_counts
)

select *
from final
