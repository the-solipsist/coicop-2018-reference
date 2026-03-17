import json
import yaml
import re

# Source: coicop_master.json
with open("coicop_master.json", "r", encoding="utf-8") as f:
    master_data = json.load(f)

nodes = master_data["nodes"]


# Custom Dumper to handle multi-line strings nicely and quote codes
class FoldedDumper(yaml.SafeDumper):
    pass


def string_representer(dumper, data):
    if re.match(r"^\d+(\.\d+)*$", data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=">")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


FoldedDumper.add_representer(str, string_representer)


# Filter codes for LLM use: only Divisions 01-13 and only up to Level 4
def is_llm_relevant(code, level):
    if level > 4:
        return False
    division = int(code[:2])
    if division > 13:
        return False
    return True


# File 1: coicop_index.yaml
index_data = {}
# Sort codes to maintain order
sorted_codes = sorted(nodes.keys())

for code in sorted_codes:
    node = nodes[code]
    if is_llm_relevant(code, node["level"]) and node["level"] <= 2:
        entry = {"title": node["title"]}
        if node.get("tags"):
            entry["product_type"] = ", ".join(node["tags"])
        if node.get("intro"):
            # Single line intro for index
            entry["intro"] = node["intro"].split("\n")[0].strip()
        index_data[code] = entry

with open("coicop_index.yaml", "w", encoding="utf-8") as f:
    yaml.dump(
        index_data,
        f,
        Dumper=FoldedDumper,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )

# File 2: coicop_detail.yaml
detail_data = {}
for code in sorted_codes:
    node = nodes[code]
    if not is_llm_relevant(code, node["level"]):
        continue

    entry = {"title": node["title"]}
    if node.get("tags"):
        entry["product_type"] = ", ".join(node["tags"])
    if node.get("intro"):
        entry["intro"] = node["intro"]

    # includes, also_includes, excludes
    # Omit any field that is empty
    for list_type in ["includes", "also_includes", "excludes"]:
        if node.get(list_type):
            items = [item["text"] for item in node[list_type]]
            if items:
                entry[list_type] = items

    detail_data[code] = entry

with open("coicop_detail.yaml", "w", encoding="utf-8") as f:
    yaml.dump(
        detail_data,
        f,
        Dumper=FoldedDumper,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )

print("Generated coicop_index.yaml and coicop_detail.yaml")
