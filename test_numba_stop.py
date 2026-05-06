import json
from scripts.paper_finviz import load_combo_params, build_engine_kwargs

params = load_combo_params("combo_pure_momentum")
kwargs = build_engine_kwargs("combo_pure_momentum", params)
print("max_stop_pct inside kwargs:", kwargs.get("max_stop_pct"))
