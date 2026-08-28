#!/usr/bin/env python3
"""Sprint 2 completion: marca las US como Done en el backlog JSON."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "docs" / "tablero_scrum_backlog.json"

# US implementadas en este push
NEW_DONE = {
    "US-03": "Done",
    "US-06": "Done",
    "US-09": "Done",
    "US-10": "Done",
    "US-11": "Done",
    "US-12": "Done",
    "US-13": "Done",
    "US-14": "Done",
}

with open(BACKLOG, "r", encoding="utf-8") as f:
    data = json.load(f)

for story in data["user_stories"]:
    if story["id"] in NEW_DONE:
        old = story.get("status", "?")
        story["status"] = NEW_DONE[story["id"]]
        print(f"  {story['id']}: {old} -> {story['status']}")

# Sprint 2 summary
data["sprint_2_summary"] = {
    "duration_weeks": 2,
    "committed_story_points": sum(
        s["story_points"] for s in data["user_stories"]
        if s.get("sprint") == 2 and s.get("status") == "Done"
    ),
    "completed_story_points": data["sprint_2_summary"]["committed_story_points"] if False else None,
}

# Recalcular Sprint 2
sp_done = sum(
    s["story_points"] for s in data["user_stories"]
    if s.get("sprint") == 2 and s.get("status") == "Done"
)
sp_total = sum(
    s["story_points"] for s in data["user_stories"]
    if s.get("sprint") == 2
)
data["sprint_2_summary"] = {
    "duration_weeks": 2,
    "committed_story_points": sp_total,
    "completed_story_points": sp_done,
}

with open(BACKLOG, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"\nSprint 2: {sp_done}/{sp_total} SP completados")
