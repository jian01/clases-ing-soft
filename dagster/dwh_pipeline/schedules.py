from dagster import AssetSelection, ScheduleDefinition, define_asset_job

daily_pipeline_job = define_asset_job(
    name="daily_pipeline",
    selection=AssetSelection.all(),
)

daily_schedule = ScheduleDefinition(
    job=daily_pipeline_job,
    cron_schedule="0 2 * * *",
    name="daily_at_2am",
)
