import pandas as pd
import json
import re

# Load the excel file
df = pd.read_excel("COICOP-2018-EN.xlsx")
df["CODE"] = df["CODE"].astype(str).str.strip()


# Function to clean and split bullet points
def parse_list(text):
    if pd.isna(text) or not str(text).strip():
        return []

    text = str(text)
    # Replace the annoying Excel line endings
    text = text.replace("_x000D_\n", "\n").replace("\r\n", "\n")

    items = []
    # Some lists use dashes, some use asterisks, some use semi-colons
    # We will split by newlines first
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove leading dash or asterisk
        line = re.sub(r"^[-*•]\s*", "", line)
        # Remove trailing semi-colons or periods
        line = re.sub(r"[;.]+$", "", line).strip()
        if line:
            items.append(line)

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
        # We'll extract ALL codes from the text for indexing/metadata
        # Pattern looks for 2 digits, optionally followed by . and 1-2 digits, e.g., 01, 01.1, 01.1.1, etc.
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
    code = str(row["CODE"]).strip()
    # Skip any empty codes or weird headers
    if not re.match(r"^\d{2}", code):
        continue

    raw_title = str(row["HEADING"]).strip()
    title, tags = extract_tags_and_title(raw_title)

    level = len(code.split("."))
    max_level = max(max_level, level)

    # Calculate parent code
    parent = None
    if level > 1:
        parent = ".".join(code.split(".")[:-1])

    intro = row["INTRODUCTORY NOTES"]
    intro = str(intro).strip() if pd.notna(intro) and str(intro).strip() else None

    includes = parse_list(row["INCLUDES"])
    also_includes = parse_list(row["INCLUDES ALSO"])
    excludes = parse_list(row["EXCLUDES"])

    # Hardcoded fix for the UN copy-paste error in 01.1.3.5
    if code == "01.1.3.5":
        includes = []

    # Hardcoded fix for 01.1.1.2 flour of cereals cross ref
    # Wait, if we use the raw Excel file, it might actually be correct in the Excel file!
    # Let's see what the Excel file actually has for 01.1.1.2... we will print it during run.

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
        "children": [],  # Will populate next
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

print(f"Generated coicop_master.json with {len(nodes)} nodes.")
