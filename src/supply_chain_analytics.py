"""Reusable analysis functions for the supply-chain portfolio project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


REQUIRED_COLUMNS: Mapping[str, set[str]] = {
    "suppliers": {
        "Supplier_ID",
        "Supplier_Name",
        "Country",
        "Lead_Time_Days",
        "On_Time_Delivery_Percent",
        "Defect_Rate_Percent",
        "Annual_Spend",
    },
    "purchase_orders": {
        "PO_Number",
        "Supplier_ID",
        "Product_ID",
        "Order_Date",
        "Expected_Delivery",
        "Actual_Delivery",
        "PO_Value",
        "Delivery_Delay_Days",
        "Status",
    },
    "inventory": {
        "Product_ID",
        "Product_Name",
        "Current_Stock",
        "Reorder_Point",
        "Inventory_Value",
    },
    "demand_history": {"Date", "Product_ID", "Demand"},
}


@dataclass(frozen=True)
class AnalysisData:
    suppliers: pd.DataFrame
    purchase_orders: pd.DataFrame
    inventory: pd.DataFrame
    demand_history: pd.DataFrame


def load_data(data_dir: str | Path) -> AnalysisData:
    """Load the four project datasets and parse their date fields."""

    root = Path(data_dir)
    suppliers = pd.read_csv(root / "suppliers.csv")
    purchase_orders = pd.read_csv(
        root / "purchase_orders.csv",
        parse_dates=["Order_Date", "Expected_Delivery", "Actual_Delivery"],
    )
    inventory = pd.read_csv(root / "inventory.csv")
    demand_history = pd.read_csv(root / "demand_history.csv", parse_dates=["Date"])
    return AnalysisData(suppliers, purchase_orders, inventory, demand_history)


def validate_data(data: AnalysisData) -> pd.DataFrame:
    """Return one validation record per dataset and fail on structural defects."""

    records: list[dict[str, object]] = []
    for name, frame in data.__dict__.items():
        missing_columns = REQUIRED_COLUMNS[name] - set(frame.columns)
        null_cells = int(frame.isna().sum().sum())
        duplicate_rows = int(frame.duplicated().sum())
        records.append(
            {
                "dataset": name,
                "rows": len(frame),
                "columns": len(frame.columns),
                "missing_required_columns": ", ".join(sorted(missing_columns)),
                "null_cells": null_cells,
                "duplicate_rows": duplicate_rows,
                "status": "PASS"
                if not missing_columns and null_cells == 0 and duplicate_rows == 0
                else "FAIL",
            }
        )
    report = pd.DataFrame(records)
    failed = report.loc[report["status"] == "FAIL"]
    if not failed.empty:
        raise ValueError(f"Data validation failed:\n{failed.to_string(index=False)}")
    return report


def _minmax(series: pd.Series, *, higher_is_better: bool = True) -> pd.Series:
    values = series.astype(float)
    spread = values.max() - values.min()
    scaled = pd.Series(50.0, index=values.index) if spread == 0 else 100 * (values - values.min()) / spread
    return scaled if higher_is_better else 100 - scaled


def build_supplier_scorecard(data: AnalysisData) -> pd.DataFrame:
    """Combine master-data quality measures with observed purchase-order performance."""

    orders = data.purchase_orders.assign(
        Is_On_Time=data.purchase_orders["Delivery_Delay_Days"].le(0)
    )
    observed = (
        orders.groupby("Supplier_ID", as_index=False)
        .agg(
            PO_Count=("PO_Number", "nunique"),
            PO_Spend=("PO_Value", "sum"),
            Observed_On_Time_Rate=("Is_On_Time", "mean"),
            Average_Delay_Days=("Delivery_Delay_Days", "mean"),
        )
        .assign(Observed_On_Time_Rate=lambda frame: 100 * frame["Observed_On_Time_Rate"])
    )
    scorecard = data.suppliers.merge(observed, on="Supplier_ID", how="left", validate="one_to_one")
    scorecard["Delivery_Component"] = _minmax(scorecard["Observed_On_Time_Rate"])
    scorecard["Quality_Component"] = _minmax(scorecard["Defect_Rate_Percent"], higher_is_better=False)
    scorecard["Lead_Time_Component"] = _minmax(scorecard["Lead_Time_Days"], higher_is_better=False)
    scorecard["Delay_Component"] = _minmax(scorecard["Average_Delay_Days"], higher_is_better=False)
    scorecard["Supplier_Score"] = (
        0.40 * scorecard["Delivery_Component"]
        + 0.25 * scorecard["Quality_Component"]
        + 0.20 * scorecard["Lead_Time_Component"]
        + 0.15 * scorecard["Delay_Component"]
    ).round(1)
    scorecard["Commercial_Risk"] = np.select(
        [
            (scorecard["Supplier_Score"] < 40) & (scorecard["PO_Spend"] >= scorecard["PO_Spend"].median()),
            scorecard["Supplier_Score"] < 55,
        ],
        ["High", "Monitor"],
        default="Controlled",
    )
    scorecard["Commercial_Risk"] = pd.Categorical(
        scorecard["Commercial_Risk"],
        categories=["High", "Monitor", "Controlled"],
        ordered=True,
    )
    return scorecard.sort_values(
        ["Commercial_Risk", "Supplier_Score", "PO_Spend"],
        ascending=[True, True, False],
    )


def classify_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    """Calculate ABC class, stockout risk and replenishment gap for every product."""

    result = inventory.sort_values("Inventory_Value", ascending=False).copy()
    total_value = result["Inventory_Value"].sum()
    result["Cumulative_Value_Percent"] = 100 * result["Inventory_Value"].cumsum() / total_value
    result["ABC_Class"] = np.select(
        [result["Cumulative_Value_Percent"] <= 80, result["Cumulative_Value_Percent"] <= 95],
        ["A", "B"],
        default="C",
    )
    result["Stockout_Risk"] = result["Current_Stock"] < result["Reorder_Point"]
    result["Reorder_Gap"] = (result["Reorder_Point"] - result["Current_Stock"]).clip(lower=0)
    result["Priority"] = np.select(
        [result["Stockout_Risk"] & result["ABC_Class"].eq("A"), result["Stockout_Risk"]],
        ["Immediate", "Review"],
        default="Routine",
    )
    return result


def _recursive_forecast(history: list[float], horizon: int, window: int) -> list[float]:
    values = list(history)
    predictions: list[float] = []
    for _ in range(horizon):
        prediction = float(np.mean(values[-window:]))
        predictions.append(prediction)
        values.append(prediction)
    return predictions


def evaluate_forecasts(demand: pd.DataFrame, holdout_months: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backtest three transparent forecasting baselines for every product."""

    prediction_rows: list[dict[str, object]] = []
    for product_id, product in demand.sort_values("Date").groupby("Product_ID"):
        product = product.sort_values("Date")
        if len(product) <= max(12, holdout_months):
            continue
        train = product.iloc[:-holdout_months]
        test = product.iloc[-holdout_months:]
        history = train["Demand"].astype(float).tolist()
        naive = _recursive_forecast(history, holdout_months, window=1)
        moving_average = _recursive_forecast(history, holdout_months, window=3)
        seasonal = product["Demand"].shift(12).iloc[-holdout_months:].astype(float).tolist()
        for row, naive_value, average_value, seasonal_value in zip(
            test.itertuples(index=False), naive, moving_average, seasonal
        ):
            prediction_rows.extend(
                [
                    {
                        "Product_ID": product_id,
                        "Date": row.Date,
                        "Actual": float(row.Demand),
                        "Model": "Naive",
                        "Forecast": naive_value,
                    },
                    {
                        "Product_ID": product_id,
                        "Date": row.Date,
                        "Actual": float(row.Demand),
                        "Model": "Moving Average 3",
                        "Forecast": average_value,
                    },
                    {
                        "Product_ID": product_id,
                        "Date": row.Date,
                        "Actual": float(row.Demand),
                        "Model": "Seasonal Naive",
                        "Forecast": seasonal_value,
                    },
                ]
            )
    predictions = pd.DataFrame(prediction_rows)
    predictions["Absolute_Error"] = (predictions["Actual"] - predictions["Forecast"]).abs()
    metrics = (
        predictions.groupby("Model", as_index=False)
        .agg(
            MAE=("Absolute_Error", "mean"),
            Total_Absolute_Error=("Absolute_Error", "sum"),
            Total_Actual=("Actual", "sum"),
        )
        .assign(WAPE=lambda frame: 100 * frame["Total_Absolute_Error"] / frame["Total_Actual"])
        .drop(columns=["Total_Absolute_Error", "Total_Actual"])
        .sort_values("WAPE")
    )
    return predictions, metrics


def executive_kpis(
    data: AnalysisData,
    supplier_scorecard: pd.DataFrame,
    inventory_analysis: pd.DataFrame,
    forecast_metrics: pd.DataFrame,
) -> pd.DataFrame:
    """Create a compact set of management KPIs for the README and outputs."""

    delayed_rate = 100 * data.purchase_orders["Delivery_Delay_Days"].gt(0).mean()
    best_model = forecast_metrics.iloc[0]
    values = [
        ("Purchase order spend", data.purchase_orders["PO_Value"].sum(), "GBP"),
        ("Delayed order rate", delayed_rate, "%"),
        ("Suppliers reviewed", data.suppliers["Supplier_ID"].nunique(), "count"),
        ("High-risk suppliers", supplier_scorecard["Commercial_Risk"].eq("High").sum(), "count"),
        ("Inventory value", data.inventory["Inventory_Value"].sum(), "GBP"),
        ("Products below reorder point", inventory_analysis["Stockout_Risk"].sum(), "count"),
        ("Immediate A-class replenishment", inventory_analysis["Priority"].eq("Immediate").sum(), "count"),
        ("Best backtest WAPE", best_model["WAPE"], "%"),
    ]
    return pd.DataFrame(values, columns=["KPI", "Value", "Unit"])
