import json
import yaml

# Source: coicop_master.json
with open("coicop_master.json", "r", encoding="utf-8") as f:
    master_data = json.load(f)

nodes = master_data["nodes"]


# Custom Dumper to handle multi-line strings nicely
class FoldedDumper(yaml.SafeDumper):
    def represent_scalar(self, tag, value, style=None):
        if tag == "tag:yaml.org,2002:str" and "\n" in value:
            return super(FoldedDumper, self).represent_scalar(tag, value, style=">")
        return super(FoldedDumper, self).represent_scalar(tag, value, style)


# File 1: coicop_index.yaml
index_data = {}
# Sort codes to maintain order
sorted_codes = sorted(nodes.keys())

for code in sorted_codes:
    node = nodes[code]
    if node["level"] <= 2:
        entry = {"title": node["title"]}
        if node.get("tags"):
            entry["product_type"] = ", ".join(node["tags"])
        if node.get("intro"):
            # Single line intro for index
            entry["intro"] = node["intro"].split("\n")[0].strip()
        index_data[code] = entry

with open("coicop_index.yaml", "w", encoding="utf-8") as f:
    yaml.dump(index_data, f, allow_unicode=True, sort_keys=False, width=1000)

# File 2: coicop_detail.yaml
detail_data = {}
for code in sorted_codes:
    node = nodes[code]
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
    f.write(
        "# Note: Level-5 codes (e.g. 01.1.1.1.1) are optional high-detail entries for Division 01 only.\n"
    )
    yaml.dump(
        detail_data,
        f,
        Dumper=FoldedDumper,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )

print("Generated coicop_index.yaml and coicop_detail.yaml")
