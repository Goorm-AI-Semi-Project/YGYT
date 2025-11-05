
# quality_checks.py
from typing import Dict

REQUIRED_KEYS = [
    "age", "gender", "nationality", "travel_type", "party_size",
    "can_wait", "budget", "spicy_ok", "is_vegetarian",
    "avoid_ingredients", "like_ingredients", "food_category"
]

def profile_completeness(profile: Dict) -> bool:
    return all(k in profile and profile[k] is not None for k in REQUIRED_KEYS)

def enforce_keywords_in_summary(summary: str, profile: Dict) -> str:
    def _has(substr: str) -> bool:
        return substr and substr.lower() in summary.lower()

    fixes = []
    if profile.get("age") and not _has(str(profile["age"])):
        fixes.append(f"(Age: {profile['age']})")
    if profile.get("party_size") and not _has(str(profile["party_size"])):
        fixes.append(f"(Group size: {profile['party_size']})")
    if profile.get("spicy_ok") and not _has("spicy"):
        if str(profile["spicy_ok"]).upper() == "O":
            fixes.append("(Okay with spicy food)")
    if profile.get("is_vegetarian") and not _has("vegetarian"):
        if str(profile["is_vegetarian"]).upper() == "X":
            fixes.append("(Not vegetarian)")
    if profile.get("avoid_ingredients") and not _has(str(profile["avoid_ingredients"])):
        fixes.append(f"(Allergy: {profile['avoid_ingredients']})")
    if profile.get("food_category") and not _has(str(profile["food_category"])):
        fixes.append(f"(Prefers {profile['food_category']})")

    if fixes:
        summary = summary.rstrip() + " " + " ".join(fixes)
    return summary
