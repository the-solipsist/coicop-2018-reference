import json
import sqlite3
import yaml

with open("coicop_master.json", "r", encoding="utf-8") as f:
    master_data = json.load(f)

nodes = master_data["nodes"]

# Generate SQLite
conn = sqlite3.connect("coicop.sqlite")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS categories")
cursor.execute("DROP TABLE IF EXISTS category_lists")

cursor.execute("""
CREATE TABLE categories (
    code TEXT PRIMARY KEY,
    parent_code TEXT,
    level INTEGER,
    title TEXT,
    intro TEXT,
    tags TEXT
)
""")

cursor.execute("""
CREATE TABLE category_lists (
    code TEXT,
    list_type TEXT,
    item_text TEXT,
    refs TEXT,
    FOREIGN KEY(code) REFERENCES categories(code)
)
""")

for code, node in nodes.items():
    cursor.execute(
        """
        INSERT INTO categories (code, parent_code, level, title, intro, tags)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            node["code"],
            node["parent"],
            node["level"],
            node["title"],
            node["intro"],
            json.dumps(node["tags"]) if node.get("tags") else None,
        ),
    )

    for list_type in ["includes", "also_includes", "excludes"]:
        if node.get(list_type):
            for item in node[list_type]:
                cursor.execute(
                    """
                    INSERT INTO category_lists (code, list_type, item_text, refs)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        node["code"],
                        list_type,
                        item["text"],
                        json.dumps(item["refs"]) if item.get("refs") else None,
                    ),
                )

conn.commit()
conn.close()
print("Generated coicop.sqlite")

# Generate YAML
# For the YAML, we want a clean representation. A flat list or a nested tree?
# YAML naturally supports nesting. We can output the flat nodes for easy parsing, or the nested tree for humans.
# "YAML (for humans) - tree structure, inline titles, readable references"


def build_yaml_tree(code):
    node = nodes[code]

    # We want a clean YAML output
    yaml_node = {"title": node["title"]}

    if node.get("tags"):
        yaml_node["tags"] = node["tags"]

    if node.get("intro"):
        yaml_node["intro"] = node["intro"]

    for list_type in ["includes", "also_includes", "excludes"]:
        if node.get(list_type):
            # For human YAML, we just output the raw text since humans don't need structured refs
            yaml_node[list_type] = [item["text"] for item in node[list_type]]

    if node.get("children") and len(node["children"]) > 0:
        yaml_node["children"] = {
            child_code: build_yaml_tree(child_code) for child_code in node["children"]
        }

    return yaml_node


root_codes = [code for code, n in nodes.items() if n["level"] == 1]
yaml_data = {
    "meta": master_data["meta"],
    "data": {code: build_yaml_tree(code) for code in root_codes},
}

# Use sort_keys=False to maintain dictionary insertion order
with open("coicop.yaml", "w", encoding="utf-8") as f:
    yaml.dump(
        yaml_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False
    )

print("Generated coicop.yaml")


# Also let's re-generate coicop.json (nested format) for backwards compatibility
def build_json_tree(code):
    node = nodes[code]
    tree_node = {
        "code": node["code"],
        "title": node["title"],
    }
    if node.get("intro"):
        tree_node["intro"] = node["intro"]

    for field in ["includes", "also_includes", "excludes"]:
        out_field = "alsoIncludes" if field == "also_includes" else field
        if node.get(field):
            tree_node[out_field] = [item["text"] for item in node[field]]

    if node.get("tags") and len(node["tags"]) > 0:
        tree_node["tags"] = node["tags"]

    if node.get("children") and len(node["children"]) > 0:
        tree_node["children"] = [
            build_json_tree(child_code) for child_code in node["children"]
        ]

    return tree_node


nested_data = [build_json_tree(code) for code in root_codes]
with open("coicop.json", "w", encoding="utf-8") as f:
    json.dump(nested_data, f, ensure_ascii=False, indent=2)

print("Generated coicop.json (nested backward-compatible version)")
