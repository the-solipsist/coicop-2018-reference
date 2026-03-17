import pandas as pd
import json
import yaml
import math
import re
import sqlite3
import html


def is_nan(val):
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if pd.isna(val):
        return True
    if str(val).strip() == "":
        return True
    return False


def parse_list_field(text):
    if is_nan(text):
        return None
    text = str(text).strip()
    if not text:
        return None
    lines = text.split("\n")
    result = []
    for line in lines:
        line = line.strip()
        line = re.sub(r"^[\*\-]\s*", "", line)
        if line:
            result.append(line)
    return result if result else None


def extract_section(text, header):
    pattern = re.compile(
        rf"(?:^|\n){header}\s*\n(.*?)(?=\n(?:Includes:|Also includes:|Excludes:)|$)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if match:
        return match.group(1), pattern.sub("", text)
    return None, text


def clean_intro(intro_text, node):
    if is_nan(intro_text):
        return None
    intro_text = str(intro_text)
    includes_text, intro_text = extract_section(intro_text, "Includes:")
    if includes_text:
        extracted = parse_list_field(includes_text)
        if extracted:
            node["includes"] = node.get("includes", []) + extracted
    also_includes_text, intro_text = extract_section(intro_text, "Also includes:")
    if also_includes_text:
        extracted = parse_list_field(also_includes_text)
        if extracted:
            node["alsoIncludes"] = node.get("alsoIncludes", []) + extracted
    excludes_text, intro_text = extract_section(intro_text, "Excludes:")
    if excludes_text:
        extracted = parse_list_field(excludes_text)
        if extracted:
            node["excludes"] = node.get("excludes", []) + extracted
    lines = intro_text.split("\n")
    lines = [line.strip() for line in lines]
    cleaned_intro = "\n".join(lines).strip()
    cleaned_intro = re.sub(r"\n{3,}", "\n\n", cleaned_intro)
    return cleaned_intro if cleaned_intro else None


def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter)


def build_tree_and_flat(df):
    records = df.to_dict("records")
    records.sort(key=lambda x: str(x["code"]))

    tree = []
    lookup = {}

    for row in records:
        code = str(row["code"]).strip()
        node = {
            "code": code,
            "title": str(row["title"]).strip() if not is_nan(row["title"]) else "",
        }
        for field in ["includes", "alsoIncludes", "excludes"]:
            parsed = parse_list_field(row[field])
            if parsed:
                node[field] = parsed
        cleaned_intro = clean_intro(row["intro"], node)
        if cleaned_intro:
            node["intro"] = cleaned_intro

        node["level"] = code.count(".") + 1
        node["parent_code"] = code.rsplit(".", 1)[0] if "." in code else None

        lookup[code] = node

        if "." not in code:
            tree.append(node)
        else:
            parent_code = node["parent_code"]
            if parent_code in lookup:
                if "children" not in lookup[parent_code]:
                    lookup[parent_code]["children"] = []
                lookup[parent_code]["children"].append(node)
            else:
                tree.append(node)

    return tree, lookup


def export_sqlite(lookup, filename="coicop.sqlite"):
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS categories")
    cursor.execute("DROP TABLE IF EXISTS category_lists")

    cursor.execute("""
        CREATE TABLE categories (
            code TEXT PRIMARY KEY,
            parent_code TEXT,
            level INTEGER,
            title TEXT,
            intro TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE category_lists (
            code TEXT,
            list_type TEXT,
            item_text TEXT,
            FOREIGN KEY(code) REFERENCES categories(code)
        )
    """)

    for code, node in lookup.items():
        cursor.execute(
            """
            INSERT INTO categories (code, parent_code, level, title, intro)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                code,
                node.get("parent_code"),
                node.get("level"),
                node.get("title"),
                node.get("intro"),
            ),
        )

        for list_type in ["includes", "alsoIncludes", "excludes"]:
            if list_type in node:
                for item in node[list_type]:
                    cursor.execute(
                        """
                        INSERT INTO category_lists (code, list_type, item_text)
                        VALUES (?, ?, ?)
                    """,
                        (code, list_type, item),
                    )

    conn.commit()
    conn.close()


def linkify(text, valid_codes):
    if not text:
        return ""
    # Escape HTML first
    text = html.escape(text)

    # Then replace code patterns with links
    def repl(m):
        code = m.group(1)
        if code in valid_codes:
            return f'<a href="classification.html#{code}">{code}</a>'
        return m.group(0)

    pattern = re.compile(r"\b(\d{2}(?:\.\d)*)\b")
    text = pattern.sub(repl, text)

    # Tooltips for acronyms
    text = re.sub(r"\bND\b", '<abbr title="Non-durables">ND</abbr>', text)
    text = re.sub(r"\bSD\b", '<abbr title="Semi-durables">SD</abbr>', text)
    text = re.sub(r"\bD\b", '<abbr title="Durables">D</abbr>', text)
    text = re.sub(r"\bS\b", '<abbr title="Services">S</abbr>', text)
    text = re.sub(
        r"\bn\.e\.c\.\b", '<abbr title="Not elsewhere classified">n.e.c.</abbr>', text
    )

    # Convert newlines to <br> or paragraphs
    text = text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    if text:
        text = f"<p>{text}</p>"
    return text


def get_html_head(title):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #f8f9fa;
            --text-color: #333;
            --border-color: #dee2e6;
            --link-color: #0056b3;
            --link-hover: #003670;
            --sidebar-width: 350px;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            margin: 0;
            padding: 0;
            display: flex;
            background: var(--bg-color);
        }}
        a {{ color: var(--link-color); text-decoration: none; }}
        a:hover {{ text-decoration: underline; color: var(--link-hover); }}
        
        .sidebar {{
            width: var(--sidebar-width);
            height: 100vh;
            position: fixed;
            overflow-y: auto;
            background: #fff;
            border-right: 1px solid var(--border-color);
            padding: 20px;
            box-sizing: border-box;
        }}
        .sidebar h2 {{ margin-top: 0; font-size: 1.2rem; }}
        .sidebar ul {{ list-style: none; padding-left: 0; margin-bottom: 20px; }}
        .sidebar li {{ margin-bottom: 8px; }}
        .sidebar a {{ display: block; font-size: 0.9rem; color: #495057; }}
        .sidebar a:hover {{ color: var(--link-color); }}
        
        .nav-links {{
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 15px;
            margin-bottom: 15px;
        }}
        .nav-links a {{ font-weight: bold; font-size: 1rem; color: var(--link-color); margin-bottom: 10px; }}
        
        .main-content {{
            margin-left: var(--sidebar-width);
            padding: 40px;
            max-width: 900px;
            width: 100%;
            box-sizing: border-box;
            background: #fff;
            min-height: 100vh;
            box-shadow: 0 0 10px rgba(0,0,0,0.05);
        }}
        
        .downloads {{
            background: #e9ecef;
            padding: 15px 20px;
            border-radius: 6px;
            margin-bottom: 30px;
            display: flex;
            gap: 15px;
            align-items: center;
        }}
        .downloads a {{
            background: #fff;
            border: 1px solid var(--border-color);
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 0.9rem;
            font-weight: bold;
        }}
        
        .node {{
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }}
        .node-01 {{ border-top: 3px solid #343a40; padding-top: 40px; margin-top: 40px; }}
        
        .code-badge {{
            background: #343a40;
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.9em;
            margin-right: 10px;
        }}
        
        h1.title, h2.title, h3.title, h4.title, h5.title, h6.title {{
            margin: 0 0 10px 0;
            font-weight: 600;
        }}
        h2.title {{ font-size: 1.8rem; margin-bottom: 15px; }}
        h3.title {{ font-size: 1.5rem; }}
        h4.title {{ font-size: 1.3rem; }}
        h5.title {{ font-size: 1.15rem; }}
        h6.title {{ font-size: 1.05rem; }}
        
        .intro {{ margin-bottom: 15px; color: #555; }}
        
        .list-box {{
            padding: 10px 15px;
            margin-bottom: 15px;
            border-radius: 4px;
            border-left: 4px solid;
        }}
        .list-box h4 {{ margin: 0 0 10px 0; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.5px; }}
        .list-box ul {{ margin: 0; padding-left: 20px; }}
        .list-box li {{ margin-bottom: 5px; }}
        
        .includes {{ background: #f0fdf4; border-color: #22c55e; }}
        .includes h4 {{ color: #166534; }}
        
        .alsoIncludes {{ background: #f0f9ff; border-color: #0ea5e9; }}
        .alsoIncludes h4 {{ color: #075985; }}
        
        .excludes {{ background: #fef2f2; border-color: #ef4444; }}
        .excludes h4 {{ color: #991b1b; }}
        
        .children {{ padding-left: 20px; border-left: 1px dashed #e5e7eb; margin-left: 10px; }}
        
        abbr {{ text-decoration: underline dotted; cursor: help; }}
    </style>
</head>
<body>
"""


def get_sidebar(tree):
    sidebar = [
        """    <div class="sidebar">
        <h2>COICOP 2018</h2>
        <p style="font-size: 0.8rem; color: #666;">Classification of Individual Consumption According to Purpose</p>
        <div class="nav-links">
            <a href="index.html">Home</a>
            <a href="guide.html">User Guide / Manual</a>
            <a href="classification.html">Interactive Classification</a>
        </div>
        <h4>Divisions</h4>
        <ul>
"""
    ]
    for node in tree:
        sidebar.append(
            f'<li><a href="classification.html#{node["code"]}"><span class="code-badge">{node["code"]}</span> {html.escape(node["title"])}</a></li>'
        )
    sidebar.append("""        </ul>
    </div>
""")
    return "\n".join(sidebar)


def generate_pages(tree, lookup):
    valid_codes = set(lookup.keys())
    sidebar_html = get_sidebar(tree)

    # 1. Generate classification.html
    html_out = [
        get_html_head("COICOP 2018 - Classification"),
        sidebar_html,
        """
    <div class="main-content">
        <h1>COICOP 2018 Reference</h1>
        <div class="downloads">
            <strong>Downloads:</strong>
            <a href="coicop.json" download>JSON</a>
            <a href="coicop.yaml" download>YAML</a>
            <a href="coicop.sqlite" download>SQLite DB</a>
        </div>
    """,
    ]

    def render_node(n, depth):
        level = n.get("level", 1)
        tag = f"h{min(level + 1, 6)}"

        cls_ext = " node-01" if level == 1 else ""

        title_html = html.escape(n["title"])
        title_html = re.sub(
            r"\bND\b", '<abbr title="Non-durables">ND</abbr>', title_html
        )
        title_html = re.sub(
            r"\bSD\b", '<abbr title="Semi-durables">SD</abbr>', title_html
        )
        title_html = re.sub(r"\bD\b", '<abbr title="Durables">D</abbr>', title_html)
        title_html = re.sub(r"\bS\b", '<abbr title="Services">S</abbr>', title_html)
        title_html = re.sub(
            r"\bn\.e\.c\.\b",
            '<abbr title="Not elsewhere classified">n.e.c.</abbr>',
            title_html,
        )

        html_out.append(f'<div class="node{cls_ext}" id="{n["code"]}">')
        html_out.append(
            f'<{tag} class="title"><span class="code-badge">{n["code"]}</span> {title_html}</{tag}>'
        )

        if n.get("intro"):
            html_out.append(
                f'<div class="intro">{linkify(n["intro"], valid_codes)}</div>'
            )

        if n.get("includes"):
            html_out.append('<div class="list-box includes"><h4>Includes</h4><ul>')
            for item in n["includes"]:
                html_out.append(f"<li>{linkify(item, valid_codes)}</li>")
            html_out.append("</ul></div>")

        if n.get("alsoIncludes"):
            html_out.append(
                '<div class="list-box alsoIncludes"><h4>Also Includes</h4><ul>'
            )
            for item in n["alsoIncludes"]:
                html_out.append(f"<li>{linkify(item, valid_codes)}</li>")
            html_out.append("</ul></div>")

        if n.get("excludes"):
            html_out.append('<div class="list-box excludes"><h4>Excludes</h4><ul>')
            for item in n["excludes"]:
                html_out.append(f"<li>{linkify(item, valid_codes)}</li>")
            html_out.append("</ul></div>")

        if n.get("children"):
            html_out.append('<div class="children">')
            for child in n["children"]:
                render_node(child, depth + 1)
            html_out.append("</div>")

        html_out.append("</div>")

    for node in tree:
        render_node(node, 1)

    html_out.append("""
    </div>
</body>
</html>
""")
    with open("classification.html", "w", encoding="utf-8") as f:
        f.write("\n".join(html_out))

    # 2. Generate index.html
    index_out = [
        get_html_head("COICOP 2018 - Home"),
        sidebar_html,
        """
    <div class="main-content">
        <h1>Welcome to COICOP 2018</h1>
        
        <div class="downloads">
            <strong>Data Downloads:</strong>
            <a href="coicop.json" download>JSON</a>
            <a href="coicop.yaml" download>YAML</a>
            <a href="coicop.sqlite" download>SQLite DB</a>
        </div>
        
        <h2>Introduction</h2>
        <p>The Classification of Individual Consumption According to Purpose (COICOP) is an integral part of the System of National Accounts (SNA). It is designed to classify individual consumption expenditures incurred by households, non-profit institutions serving households (NPISH), and general government.</p>
        
        <p>COICOP is used in several statistical areas such as:</p>
        <ul>
            <li>Household expenditure statistics based on household budget surveys</li>
            <li>Consumer price indices (to establish weights and aggregate prices)</li>
            <li>International comparisons of gross domestic product (GDP) and purchasing power parities</li>
            <li>Statistics relating to culture, sports, food, health, and tourism</li>
        </ul>

        <h2>Structure</h2>
        <p>COICOP 2018 has a hierarchical structure consisting of four levels:</p>
        <ul>
            <li><strong>Division</strong> (2-digit level, e.g. <code>03</code> Clothing and footwear)</li>
            <li><strong>Group</strong> (3-digit level, e.g. <code>03.1</code> Clothing)</li>
            <li><strong>Class</strong> (4-digit level, e.g. <code>03.1.1</code> Clothing materials)</li>
            <li><strong>Subclass</strong> (5-digit level, e.g. <code>03.1.1.0</code> Clothing materials)</li>
        </ul>

        <h2>Acronyms</h2>
        <p>COICOP 2018 class and subclass levels are also divided into the following designations, which provide elements for other analytic applications (such as estimating the stock of capital goods held by households):</p>
        <ul>
            <li><strong><abbr title="Services">S</abbr></strong>: Services</li>
            <li><strong><abbr title="Non-durables">ND</abbr></strong>: Non-durables</li>
            <li><strong><abbr title="Semi-durables">SD</abbr></strong>: Semi-durables</li>
            <li><strong><abbr title="Durables">D</abbr></strong>: Durables</li>
            <li><strong><abbr title="Not elsewhere classified">n.e.c.</abbr></strong>: Not elsewhere classified</li>
        </ul>

        <h2>PDF Manual</h2>
        <p>You can read the <a href="guide.html">HTML Guide</a> we extracted from the PDF, or <a href="COICOP_2018_-_pre-edited_white_cover_version_-_2018-12-26.pdf" target="_blank">download the original PDF</a> directly.</p>
    </div>
</body>
</html>
""",
    ]
    with open("index.html", "w", encoding="utf-8") as f:
        f.write("\n".join(index_out))

    # 3. Generate guide.html
    with open("guide_content.html", "r", encoding="utf-8") as f:
        guide_content = f.read()

    guide_out = [
        get_html_head("COICOP 2018 - Guide"),
        sidebar_html,
        f"""
    <div class="main-content">
        <h1>COICOP 2018 User Guide</h1>
        {guide_content}
    </div>
</body>
</html>
""",
    ]
    with open("guide.html", "w", encoding="utf-8") as f:
        f.write("\n".join(guide_out))


def main():
    print("Reading excel...")
    df = pd.read_excel("COICOP_2018_English_structure_edited.xlsx", dtype={"code": str})

    print("Building tree...")
    tree, lookup = build_tree_and_flat(df)

    # Remove parent_code and level from tree dump so we don't pollute the JSON/YAML needlessly
    def clean_tree_for_export(nodes):
        for node in nodes:
            node.pop("level", None)
            node.pop("parent_code", None)
            if "children" in node:
                clean_tree_for_export(node["children"])

    export_tree = json.loads(json.dumps(tree))  # Deep copy
    clean_tree_for_export(export_tree)

    print("Writing JSON...")
    with open("coicop.json", "w", encoding="utf-8") as f:
        json.dump(export_tree, f, indent=2, ensure_ascii=False)

    print("Writing YAML...")
    with open("coicop.yaml", "w", encoding="utf-8") as f:
        yaml.dump(
            export_tree,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=float("inf"),
        )

    print("Writing SQLite...")
    export_sqlite(lookup)

    print("Writing HTML...")
    generate_pages(tree, lookup)

    print("Done!")


if __name__ == "__main__":
    main()
