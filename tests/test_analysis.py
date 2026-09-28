from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supply_chain_analytics import (  # noqa: E402
    AnalysisData,
    build_supplier_scorecard,
    classify_inventory,
    evaluate_forecasts,
    validate_data,
)


def test_abc_classification_preserves_total_value() -> None:
    inventory = pd.DataFrame(
        {
            "Product_ID": ["A", "B", "C"],
            "Product_Name": ["A", "B", "C"],
            "Current_Stock": [1, 10, 3],
            "Reorder_Point": [5, 5, 3],
            "Inventory_Value": [80.0, 15.0, 5.0],
        }
    )
    result = classify_inventory(inventory)
    assert result["Inventory_Value"].sum() == 100.0
    assert result.loc[result["Product_ID"] == "A", "Priority"].item() == "Immediate"
    assert set(result["ABC_Class"]) == {"A", "B", "C"}


def test_forecast_backtest_returns_all_models() -> None:
    dates = pd.date_range("2024-01-01", periods=15, freq="MS")
    demand = pd.DataFrame(
        {
            "Date": dates,
            "Product_ID": ["P1"] * len(dates),
            "Demand": [100 + (month % 12) * 5 for month in range(len(dates))],
        }
    )
    predictions, metrics = evaluate_forecasts(demand, holdout_months=3)
    assert len(predictions) == 9
    assert set(metrics["Model"]) == {"Naive", "Moving Average 3", "Seasonal Naive"}
    assert metrics["WAPE"].notna().all()


def test_validation_and_supplier_scores() -> None:
    suppliers = pd.DataFrame(
        {
            "Supplier_ID": ["S1", "S2"],
            "Supplier_Name": ["One", "Two"],
            "Country": ["UK", "DE"],
            "Lead_Time_Days": [10, 20],
            "On_Time_Delivery_Percent": [95.0, 70.0],
            "Defect_Rate_Percent": [1.0, 5.0],
            "Annual_Spend": [1000.0, 2000.0],
        }
    )
    orders = pd.DataFrame(
        {
            "PO_Number": ["P1", "P2"],
            "Supplier_ID": ["S1", "S2"],
            "Product_ID": ["A", "B"],
            "Order_Date": pd.to_datetime(["2026-01-01", "2026-01-01"]),
            "Expected_Delivery": pd.to_datetime(["2026-01-10", "2026-01-10"]),
            "Actual_Delivery": pd.to_datetime(["2026-01-10", "2026-01-15"]),
            "PO_Value": [1000.0, 2000.0],
            "Delivery_Delay_Days": [0, 5],
            "Status": ["On Time", "Delayed"],
        }
    )
    inventory = pd.DataFrame(
        {
            "Product_ID": ["A"],
            "Product_Name": ["A"],
            "Current_Stock": [5],
            "Reorder_Point": [10],
            "Inventory_Value": [100.0],
        }
    )
    demand = pd.DataFrame(
        {
            "Date": pd.date_range("2025-01-01", periods=13, freq="MS"),
            "Product_ID": ["A"] * 13,
            "Demand": list(range(13)),
        }
    )
    data = AnalysisData(suppliers, orders, inventory, demand)
    assert validate_data(data)["status"].eq("PASS").all()
    scorecard = build_supplier_scorecard(data)
    assert len(scorecard) == 2
    assert scorecard["Supplier_Score"].between(0, 100).all()
    assert scorecard.iloc[0]["Commercial_Risk"] == "High"
