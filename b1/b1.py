import json

with open("data/festival.json", encoding="utf-8") as file:
    festival = json.load(file)

performances = festival["performances"]

# ---------- Step 00: summary ----------
print(festival["name"])
print(f"From {festival['first_day']} to {festival['last_day']}")
print(
    f"{len(festival['venues'])} venues, "
    f"{len(festival['artists'])} artists, "
    f"{len(performances)} performances"
)
print()

# ---------- Step 01 ----------
# 1. Venues and total seats
print("Venues:")
total_seats = 0
for venue in festival["venues"]:
    print(f"- {venue['name']}: {venue['capacity']} seats ({venue['address']})")
    total_seats += venue["capacity"]
print(f"Total: {total_seats} seats")
print()

# 2. Performances per kind
counts = {}
for performance in performances:
    kind = performance["kind"]
    counts[kind] = counts.get(kind, 0) + 1
for kind, number in counts.items():
    print(f"{kind}: {number}")
print()

# 3. Performances at Le Kiosque ("venue" holds a slug, not the name)
print("At Le Kiosque:")
for performance in performances:
    if performance["venue"] == "le-kiosque":
        print(f"- {performance['start']} {performance['title']}")
print()

# 4. Longest performance
longest = performances[0]
for performance in performances:
    if performance["duration_minutes"] > longest["duration_minutes"]:
        longest = performance
print(f"Longest: {longest['title']} ({longest['duration_minutes']} min)")
print()

# 5. Workshops
for performance in performances:
    if performance["kind"] == "workshop":
        day = performance["start"][:10]
        registered = len(performance["participants"])
        places = performance["max_participants"]
        print(f"{performance['title']} on {day}: {registered}/{places} registered")
print()

# 6. [ext.] Artists on stage the most often
appearances = {}
for performance in performances:
    slugs = []
    if performance["kind"] == "solo":
        slugs.append(performance["artist"])
    elif performance["kind"] == "lineup":
        slugs.append(performance["host"])
        slugs.extend(performance["acts"])
    elif performance["kind"] == "workshop":
        slugs.append(performance["teacher"])
    for slug in slugs:
        appearances[slug] = appearances.get(slug, 0) + 1

most = max(appearances.values())
leaders = []
for slug, number in appearances.items():
    if number == most:
        leaders.append(slug)
print(f"On stage {most} times: {', '.join(leaders)}")
print()

# ---------- Step 02: the programme of a day ----------
# The days of the festival, found from the data
days = []
for performance in performances:
    day = performance["start"][:10]
    if day not in days:
        days.append(day)

# Ask until the answer is one of the days
answer = input("Day (YYYY-MM-DD): ").strip()
while answer not in days:
    print(f"No performance on '{answer}'. Days: {', '.join(days)}")
    answer = input("Day (YYYY-MM-DD): ").strip()

# Venue names, found from the slug
venue_names = {}
for venue in festival["venues"]:
    slug = venue["name"].lower().replace(" ", "-").replace("é", "e").replace("â", "a")
    venue_names[slug] = venue["name"]

# The programme of the day
print(f"Programme for {answer}:")
for performance in performances:
    if performance["start"][:10] == answer:
        time = performance["start"][11:]
        venue_name = venue_names[performance["venue"]]
        print(f"{time} | {venue_name} | {performance['title']} ({performance['kind']})")
