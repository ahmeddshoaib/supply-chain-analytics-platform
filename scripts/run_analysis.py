"""Run the full analysis and write decision-ready outputs."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supply_chain_analytics import (  # noqa: E402
    build_supplier_scorecard,
    classify_inventory,
    evaluate_forecasts,
    executive_kpis,
    load_data,
    validate_data,
)


NAVY = "#16324F"
BLUE = "#2E6F9E"
ORANGE = "#D97706"
GREY = "#64748B"


def save_charts(
    scorecard: pd.DataFrame,
    inventory: pd.DataFrame,
    predictions: pd.DataFrame,
    output_dir: Path,
) -> None:
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(10, 6))
    sizes = 60 + 260 * scorecard["PO_Spend"] / scorecard["PO_Spend"].max()
    scatter = ax.scatter(
        scorecard["Observed_On_Time_Rate"],
        scorecard["Defect_Rate_Percent"],
        s=sizes,
        c=scorecard["Supplier_Score"],
        cmap="RdYlGn",
        alpha=0.82,
        edgecolor="white",
        linewidth=0.8,
    )
    fig.suptitle("Supplier Performance and Spend Exposure", fontsize=17, y=0.98)
    ax.set_title("Bubble size represents purchase-order spend; colour shows composite supplier score", fontsize=10.5)
    ax.set(xlabel="Observed on-time rate (%)", ylabel="Defect rate (%)")
    colour_bar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colour_bar.set_label("Supplier score")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(figures / "supplier_performance.png", dpi=180)
    plt.close(fig)

    abc = inventory.groupby("ABC_Class", as_index=False).agg(
        Products=("Product_ID", "count"), Inventory_Value=("Inventory_Value", "sum")
    )
    abc["ABC_Class"] = pd.Categorical(abc["ABC_Class"], ["A", "B", "C"], ordered=True)
    abc = abc.sort_values("ABC_Class")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(abc["ABC_Class"].astype(str), abc["Inventory_Value"] / 1_000_000, color=[NAVY, BLUE, GREY])
    ax.set(title="Inventory Value by ABC Class", xlabel="ABC class", ylabel="Inventory value (£m)")
    for index, value in enumerate(abc["Inventory_Value"] / 1_000_000):
        ax.text(index, value + 0.35, f"£{value:.2f}m", ha="center", va="bottom", fontsize=10)
    fig.tight_layout()
    fig.savefig(figures / "abc_inventory_value.png", dpi=180)
    plt.close(fig)

    aggregate = predictions.groupby(["Date", "Model"], as_index=False).agg(Actual=("Actual", "sum"), Forecast=("Forecast", "sum"))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    actual = aggregate.drop_duplicates("Date")
    ax.plot(actual["Date"], actual["Actual"], color=NAVY, marker="o", linewidth=2.5, label="Actual")
    for model, colour in [("Naive", GREY), ("Moving Average 3", ORANGE), ("Seasonal Naive", BLUE)]:
        subset = aggregate.loc[aggregate["Model"] == model]
        ax.plot(subset["Date"], subset["Forecast"], marker="o", linewidth=1.8, label=model, color=colour)
    ax.set(title="Three-Month Aggregate Demand Backtest", xlabel="Month", ylabel="Demand units")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(figures / "forecast_backtest.png", dpi=180)
    plt.close(fig)


def main() -> None:
    output_dir = ROOT / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_data(ROOT / "data")
    validation = validate_data(data)
    scorecard = build_supplier_scorecard(data)
    inventory = classify_inventory(data.inventory)
    predictions, forecast_metrics = evaluate_forecasts(data.demand_history)
    kpis = executive_kpis(data, scorecard, inventory, forecast_metrics)

    validation.to_csv(output_dir / "data_quality_report.csv", index=False)
    scorecard.to_csv(output_dir / "supplier_scorecard.csv", index=False)
    inventory.to_csv(output_dir / "inventory_priorities.csv", index=False)
    predictions.to_csv(output_dir / "forecast_backtest_predictions.csv", index=False)
    forecast_metrics.to_csv(output_dir / "forecast_metrics.csv", index=False)
    kpis.to_csv(output_dir / "executive_kpis.csv", index=False)
    save_charts(scorecard, inventory, predictions, output_dir)

    summary = {
        "validation": validation.to_dict(orient="records"),
        "kpis": kpis.to_dict(orient="records"),
        "forecast_models": forecast_metrics.round(3).to_dict(orient="records"),
    }
    (output_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(kpis.to_string(index=False))
    print("\nForecast backtest")
    print(forecast_metrics.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
