-- Source: dbt_marketo
-- Model: int_marketo__lead
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/int_marketo__lead.sql

with leads as(
    select *
    from leads

), activity_merge_leads as (
    select *
    from activity_merge_leads

), unique_merges as (

    select
        source_relation,
        cast(lead_id as INT) as lead_id,
        max(new_value) as merged_into_lead_id

    from activity_merge_leads
    group by 1, 2

/*If you do not use the activity_delete_lead table, set var marketo__activity_delete_lead_enabled
to False. Default is True*/

), joined as (

    select
        leads.*,

        /*If you do not use the activity_delete_lead table, set var marketo__activity_delete_lead_enabled
        to False. Default is True*/

        unique_merges.merged_into_lead_id,
        case when unique_merges.merged_into_lead_id is not null then True else False end as is_merged
    from leads

    /*If you do not use the activity_delete_lead table, set var marketo__activity_delete_lead_enabled
    to False. Default is True*/

    left join unique_merges
        on leads.source_relation = unique_merges.source_relation
        and leads.lead_id = unique_merges.lead_id
)

select *
from joined