from pathlib import Path

from dagster_dbt import DbtCliResource

DBT_PROJECT_DIR = Path("/workspace/dbt")

dbt_resource = DbtCliResource(project_dir=str(DBT_PROJECT_DIR))
