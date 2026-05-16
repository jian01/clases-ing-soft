"""
Assets del pipeline DWH de streaming.

Tres grupos:
  extract   → carga CSVs a bronze
  transform → modelos silver + dimensiones gold (full-refresh, sin particion)
  gold      → fact_streams (incremental, particionado por fecha)
"""
import json
import sys
from pathlib import Path

from dagster import AssetExecutionContext, asset
from dagster_dbt import DbtCliResource, dbt_assets

DBT_PROJECT_DIR = Path("/workspace/dbt")
DBT_MANIFEST = DBT_PROJECT_DIR / "target" / "manifest.json"


@asset(
    group_name="extract",
    description="Carga los CSVs de /workspace/data a la capa bronze de Postgres.",
)
def extract_to_bronze(context: AssetExecutionContext) -> None:
    sys.path.insert(0, "/workspace/extract")
    from load_to_bronze import load_all_csvs  # type: ignore

    total = load_all_csvs(logger=context.log)
    context.add_output_metadata({"filas_cargadas": total})


@dbt_assets(
    manifest=DBT_MANIFEST,
    select="fact_streams",
)
def dbt_fact_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """fact_streams: full-refresh por defecto. Para reprocesar un dia:
    pasá run_date via op_config o desde la UI en Run Config > ops > dbt_fact_assets."""
    run_date = context.op_config.get("run_date") if context.op_config else None
    cmd = ["build", "--select", "fact_streams"]
    if run_date:
        cmd += ["--vars", json.dumps({"run_date": run_date})]
    yield from dbt.cli(cmd, context=context).stream()


@dbt_assets(
    manifest=DBT_MANIFEST,
    exclude="fact_streams",
)
def dbt_dim_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Modelos silver + dimensiones gold (full-refresh)."""
    yield from dbt.cli(
        ["build", "--exclude", "fact_streams"],
        context=context,
    ).stream()


all_assets = [extract_to_bronze, dbt_fact_assets, dbt_dim_assets]
