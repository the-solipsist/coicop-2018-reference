import pandas as pd
import json
import re

# Load the authoritative excel file
SOURCE_FILE = "COICOP_2018_English_structure.xlsx"
df = pd.read_excel(SOURCE_FILE)

# Remove Excel XML artifacts and Windows line endings globally
for col in df.columns:
    if df[col].dtype == "object":
        # Remove _x000D_, _x000A_, etc.
        df[col] = df[col].astype(str).str.replace(r"_x[0-9A-F]{4}_", "", regex=True)
        # Also catch x000D if underscores were stripped somehow
        df[col] = df[col].str.replace("x000D", "", regex=False)
        # Replace non-breaking spaces (\xa0) with standard spaces
        df[col] = df[col].str.replace("\xa0", " ", regex=False)
        # Normalize en-dashes and smart quotes
        df[col] = df[col].str.replace("–", "-", regex=False)
        df[col] = df[col].str.replace("’", "'", regex=False)
        df[col] = df[col].str.replace("“", '"', regex=False)
        df[col] = df[col].str.replace("”", '"', regex=False)
        # Convert "nan" strings back to actual NaN
        df.loc[df[col] == "nan", col] = pd.NA

df["code"] = df["code"].astype(str).str.strip()


# Function to clean and split bullet points
def parse_list(text):
    if pd.isna(text) or not str(text).strip():
        return []

    text = str(text)
    # Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    items = []
    # Split by newlines or bullets
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Split further if multiple items are on one line separated by bullets
        sublines = re.split(r"(?=[-*•])", line)
        for sl in sublines:
            sl = sl.strip()
            if not sl:
                continue
            # Remove leading dash or asterisk
            sl = re.sub(r"^[-*•]\s*", "", sl)
            # Remove trailing semi-colons or periods
            sl = re.sub(r"[;.]+$", "", sl).strip()
            if sl:
                items.append(sl)

    return items


def extract_tags_and_title(title):
    tags = []
    # Look for (ND), (SD), (D), (S)
    tag_match = re.search(r"\((ND|SD|D|S)\)", title)
    if tag_match:
        tags.append(tag_match.group(1))
        # Remove it from title
        title = title.replace(tag_match.group(0), "").strip()
    return title.strip(), tags


def parse_cross_references(items):
    parsed_items = []
    for item in items:
        # Extract ALL codes from the text for indexing/metadata
        refs = re.findall(r"\b(\d{2}(?:\.\d{1,2})*)\b", item)
        # Also handle "Division 11"
        div_refs = re.findall(r"Division\s+(\d{2})", item, re.IGNORECASE)
        refs.extend(div_refs)

        # Deduplicate
        refs = list(set(refs))

        parsed_items.append({"text": item, "refs": refs})
    return parsed_items


nodes = {}
max_level = 0

for idx, row in df.iterrows():
    code = str(row["code"]).strip()
    if not re.match(r"^\d{2}", code):
        continue

    raw_title = str(row["title"]).strip()
    title, tags = extract_tags_and_title(raw_title)

    level = len(code.split("."))
    max_level = max(max_level, level)

    parent = None
    if level > 1:
        parent = ".".join(code.split(".")[:-1])

    intro = row["intro"]
    intro = str(intro).strip() if pd.notna(intro) and str(intro).strip() else None

    includes = parse_list(row["includes"])
    also_includes = parse_list(row["alsoIncludes"])
    excludes = parse_list(row["excludes"])

    node = {
        "code": code,
        "parent": parent,
        "level": level,
        "title": title,
        "intro": intro,
        "includes": parse_cross_references(includes),
        "also_includes": parse_cross_references(also_includes),
        "excludes": parse_cross_references(excludes),
        "tags": tags,
        "children": [],
    }

    nodes[code] = node

# Populate children arrays
for code, node in nodes.items():
    if node["parent"]:
        if node["parent"] in nodes:
            nodes[node["parent"]]["children"].append(code)
        else:
            print(f"Warning: Parent {node['parent']} not found for {code}")

master_json = {
    "meta": {
        "name": "COICOP 2018",
        "version": "2018",
        "source": "United Nations Statistics Division",
        "levels": ["Division", "Group", "Class", "Subclass", "Sub-subclass"][
            :max_level
        ],
    },
    "nodes": nodes,
}

with open("coicop_master.json", "w", encoding="utf-8") as f:
    json.dump(master_json, f, ensure_ascii=False, indent=2)

print(f"Generated coicop_master.json with {len(nodes)} nodes from {SOURCE_FILE}.")
