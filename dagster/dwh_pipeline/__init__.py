from dagster import Definitions

from .assets import all_assets
from .resources import dbt_resource
from .schedules import daily_schedule

defs = Definitions(
    assets=all_assets,
    schedules=[daily_schedule],
    resources={"dbt": dbt_resource},
)
