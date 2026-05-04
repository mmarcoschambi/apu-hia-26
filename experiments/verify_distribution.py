import pandas as pd
from pathlib import Path

# Load the latest dataset
dataset_path = "outputs/experiments/sector_strength_sizing_dataset_20260504_024632.parquet"
df = pd.read_parquet(dataset_path)

# Split into train and validation
train = df[df["date"] <= "2025-09-30"].copy()
val = df[df["date"] >= "2025-10-01"].copy()

def get_stats(sub_df, label):
    counts = sub_df["sector_strength_bucket"].value_counts(normalize=True).sort_index()
    rets = sub_df.groupby("sector_strength_bucket", observed=True)["fwd_20d"].mean()
    sharpes = sub_df.groupby("sector_strength_bucket", observed=True).apply(
        lambda x: (x["r_20d"].mean() / x["r_20d"].std() * (252/20)**0.5) if len(x) > 1 and x["r_20d"].std() != 0 else 0
    )
    
    stats = pd.DataFrame({
        "weight": counts,
        "mean_ret_20d": rets,
        "sharpe_20d": sharpes
    })
    print(f"\n--- {label.upper()} Stats ---")
    print(stats)
    return stats

train_stats = get_stats(train, "train")
val_stats = get_stats(val, "validation")

# Check for concentration/regime shift
weight_diff = val_stats["weight"] - train_stats["weight"]
ret_diff = val_stats["mean_ret_20d"] - train_stats["mean_ret_20d"]

print("\n--- DIFFERENCE (VAL - TRAIN) ---")
print("Weight Diff:")
print(weight_diff)
print("\nMean Return Diff:")
print(ret_diff)
