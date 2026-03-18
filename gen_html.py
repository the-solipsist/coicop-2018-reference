import json

with open("coicop_master.json", "r", encoding="utf-8") as f:
    master_data = json.load(f)

nodes = master_data["nodes"]


# Build nested tree for the UI
def build_tree(code):
    node = nodes[code]
    tree_node = {
        "code": node["code"],
        "title": node["title"],
    }
    if node.get("intro"):
        tree_node["intro"] = node["intro"]

    # In the UI, includes/excludes were just arrays of strings. Let's convert them back to raw HTML strings or just text.
    # The new structured format has {"text": "...", "refs": [...]}. We can just use the text and add the links in JS,
    # OR we can just pass the structured array. Let's adapt the JS slightly, but passing text + refs is great.

    # Wait, the JS currently does formatText() with regex anyway! So we can just pass the raw text as strings to minimize JS changes.
    for field in ["includes", "also_includes", "excludes"]:
        # Note: the old JSON used 'alsoIncludes', new master uses 'also_includes'
        out_field = "alsoIncludes" if field == "also_includes" else field
        if node.get(field):
            tree_node[out_field] = [item["text"] for item in node[field]]

    if node.get("tags") and len(node["tags"]) > 0:
        # Re-attach tags to title, or add a tags array.
        # Actually, if we just pass a tags array, we can update the JS to render it!
        tree_node["tags"] = node["tags"]

    if node.get("children") and len(node["children"]) > 0:
        tree_node["children"] = [
            build_tree(child_code) for child_code in node["children"]
        ]

    return tree_node


# Only top-level divisions
root_codes = [code for code, n in nodes.items() if n["level"] == 1]
nested_data = [build_tree(code) for code in root_codes]

# Create a flat map of code -> title for tooltips
code_title_map = {code: node["title"] for code, node in nodes.items()}

json_str = json.dumps(nested_data, ensure_ascii=False).replace(
    "</script>", "<\\/script>"
)
code_title_map_json = json.dumps(code_title_map, ensure_ascii=False).replace(
    "</script>", "<\\/script>"
)

html_template = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>COICOP 2018 - Classification</title>
    <style>
        :root {
            --toc-width: 380px;
            --link-color: #0066cc;
            --link-hover: #004499;
            --bg-color: #fff;
            --border-color: #e9ecef;
        }
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 0;
            background: #fff;
        }
        a { color: var(--link-color); text-decoration: none; }
        a:hover { text-decoration: underline; color: var(--link-hover); }
        
        .top-nav {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: #fff;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            padding: 0 20px;
            z-index: 200;
        }
        .top-nav h1 { margin: 0; font-size: 1.2rem; font-weight: 600; }
        .top-nav .nav-links { margin-left: 30px; display: flex; gap: 20px; }
        .top-nav .nav-links a { font-size: 0.95rem; color: #555; font-weight: 500; }
        .top-nav .nav-links a:hover { color: var(--link-color); }
        .top-nav .nav-links a.active { color: var(--link-color); border-bottom: 2px solid var(--link-color); padding-bottom: 18px; margin-bottom: -20px; }
        
        .top-nav .downloads { margin-left: auto; display: flex; gap: 10px; align-items: center; }
        .top-nav .downloads span { font-size: 0.85rem; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .top-nav .downloads a {
            font-size: 0.8rem;
            color: #444;
            border: 1px solid #ccc;
            padding: 4px 8px;
            border-radius: 4px;
            background: #f8f9fa;
        }
        .top-nav .downloads a:hover {
            background: #e9ecef;
            color: #000;
            border-color: #999;
            text-decoration: none;
        }
        
        .toc-sidebar {
            position: fixed;
            top: 60px;
            left: 0;
            width: var(--toc-width);
            height: calc(100vh - 60px);
            background: #fafafa;
            border-right: 1px solid var(--border-color);
            padding: 15px 0 0 0;
            z-index: 100;
            display: flex;
            flex-direction: column;
        }
        
        #toc-container {
            flex: 1;
            overflow-y: auto;
            padding-bottom: 15px;
        }
        
        .level-filter {
            padding: 0 15px 15px 15px;
            margin-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            color: #666;
        }
        .level-filter select { padding: 3px 6px; font-size: 0.85rem; border: 1px solid #ccc; border-radius: 3px; }
        
        .toc-sidebar h2 {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #888;
            padding: 0 15px;
            margin: 0 0 10px 0;
        }
        
        .toc-list { list-style: none; padding: 0; margin: 0; }
        .toc-list .toc-list { padding-left: 15px; display: none; }
        .toc-item.expanded > .toc-list { display: block; }
        
        .toc-row { 
            display: flex; 
            align-items: flex-start; 
            padding: 4px 10px 4px 5px; 
            border-left: 3px solid transparent;
        }
        .toc-row:hover { background: #f0f0f0; }
        .toc-row.active { background: #e6f0ff; border-left-color: #0066cc; }
        .toc-row.active .toc-link { color: #0066cc; font-weight: 500; }
        
        .toc-toggle { 
            cursor: pointer; 
            display: inline-flex; 
            align-items: center;
            justify-content: center;
            width: 20px; 
            height: 20px;
            font-size: 0.65rem; 
            color: #666; 
            user-select: none; 
            transition: transform 0.2s; 
            flex-shrink: 0;
            margin-right: 2px;
            border-radius: 3px;
        }
        .toc-toggle:hover { background: #e0e0e0; color: #000; }
        .toc-item.expanded > .toc-row > .toc-toggle { transform: rotate(90deg); }
        .toc-toggle-empty { display: inline-block; width: 22px; flex-shrink: 0; }
        
        .toc-link { 
            display: flex; 
            text-decoration: none; 
            color: #444; 
            flex: 1; 
            align-items: baseline; 
            gap: 8px;
            cursor: pointer;
        }
        .toc-link .code { font-family: monospace; font-size: 0.85rem; color: #666; flex-shrink: 0; }
        .toc-link .title { font-size: 0.85rem; line-height: 1.3; }
        
        .main-content {
            margin-left: var(--toc-width);
            margin-top: 60px;
            padding: 30px 50px;
            max-width: 1000px;
        }
        
        .content-item { margin-bottom: 30px; padding-top: 20px; scroll-margin-top: 80px; }
        
        .content-item h2 { margin: 0 0 10px 0; font-size: 1.8rem; font-weight: 700; color: #111; }
        .content-item h2 .code { font-weight: normal; color: #666; font-size: 1.3rem; margin-left: 10px; font-family: monospace; }
        
        .content-item h3 { margin: 25px 0 10px 0; font-size: 1.5rem; font-weight: 600; color: #222; }
        .content-item h3 .code { font-weight: normal; color: #666; font-size: 1.1rem; margin-left: 10px; font-family: monospace; }
        
        .content-item h4 { margin: 20px 0 8px 0; font-size: 1.3rem; font-weight: 600; color: #333; }
        .content-item h4 .code { font-weight: normal; color: #666; font-size: 1rem; margin-left: 8px; font-family: monospace; }

        .content-item h5 { margin: 15px 0 6px 0; font-size: 1.15rem; font-weight: 600; color: #444; }
        .content-item h5 .code { font-weight: normal; color: #666; font-size: 0.95rem; margin-left: 8px; font-family: monospace; }

        .content-item h6 { margin: 15px 0 6px 0; font-size: 1.05rem; font-weight: 600; color: #555; }
        .content-item h6 .code { font-weight: normal; color: #666; font-size: 0.9rem; margin-left: 8px; font-family: monospace; }
        
        .content-description { margin: 8px 0 15px 0; color: #444; line-height: 1.6; white-space: pre-line; }
        
        .collapsible { margin: 8px 0; }
        .collapsible summary {
            cursor: pointer;
            font-weight: 500;
            font-size: 0.9rem;
            color: #555;
            outline: none;
            padding: 3px 0;
        }
        .collapsible summary:hover { color: #333; }
        .collapsible[open] summary { margin-bottom: 5px; }
        .collapsible .includes { color: #2e7d32; }
        .collapsible .excludes { color: #c62828; }
        .collapsible ul { margin: 5px 0; padding-left: 20px; }
        .collapsible li { margin-bottom: 3px; font-size: 0.9rem; }
        
        @media (max-width: 900px) {
            .toc-sidebar { display: none; }
            .main-content { margin-left: 0; padding: 20px; }
            .top-nav { padding: 0 10px; }
            .top-nav .nav-links { margin-left: 10px; gap: 10px; }
            .top-nav .downloads { display: none; }
        }
    </style>
</head>
<body>
    <div class="top-nav">
        <h1>COICOP 2018</h1>
        <div class="nav-links">
            <a href="index.html">Home</a>
            <a href="guide.html">Guide</a>
            <a href="classification.html" class="active">Classification</a>
        </div>
        <div class="downloads">
            <span>Downloads:</span>
            <a href="coicop.json" download>JSON</a>
            <a href="coicop.yaml" download>YAML</a>
            <a href="coicop.sqlite" download>SQLite</a>
        </div>
    </div>

    <nav class="toc-sidebar">
        <div class="level-filter">
            <label>Show Depth:</label>
            <select id="level-select">
                <option value="1">Divisions</option>
                <option value="2" selected>Groups</option>
                <option value="3">Classes</option>
                <option value="4">Subclasses</option>
                <option value="5">Full</option>
            </select>
        </div>
        <h2>Contents</h2>
        <div id="toc-container"></div>
    </nav>

    <div class="main-content">
        <div id="content-container"></div>
    </div>

    <script>
        const coicopData = __JSON_DATA__;
        const codeTitleMap = __CODE_TITLE_MAP__;
        
        function getLevel(code) {
            if (code.includes('.')) return code.split('.').length;
            return 1;
        }
        
        function flattenData(data, maxLevel, result = []) {
            for (const item of data) {
                const level = getLevel(item.code);
                if (level <= maxLevel) {
                    result.push(item);
                    if (item.children && level < maxLevel) {
                        flattenData(item.children, maxLevel, result);
                    }
                }
            }
            return result;
        }
        
        function toggleTOC(el, event) {
            event.stopPropagation();
            event.preventDefault();
            const li = el.closest('.toc-item');
            if (li) {
                li.classList.toggle('expanded');
            }
        }

        function renderTOC(data, container, maxLevel) {
            let html = `<ul class="toc-list">`;
            for (const item of data) {
                const itemLevel = getLevel(item.code);
                const hasChildren = item.children && item.children.length > 0;
                // Auto-expand based on maxLevel selection
                const isExpanded = itemLevel < maxLevel;
                
                html += `<li class="toc-item ${hasChildren ? 'has-children' : ''} ${isExpanded ? 'expanded' : ''}">
                    <div class="toc-row" data-code="${item.code}">
                        ${hasChildren ? `<span class="toc-toggle" onclick="toggleTOC(this, event)">▶</span>` : `<span class="toc-toggle-empty"></span>`}
                        <a class="toc-link" href="#${item.code}">
                            <span class="code">${item.code}</span>
                            <span class="title">${item.title}</span>
                        </a>
                    </div>`;
                
                if (hasChildren) {
                    html += renderTOC(item.children, null, maxLevel);
                }
                html += '</li>';
            }
            html += '</ul>';
            if (container) container.innerHTML = html;
            return html;
        }
        
        function escapeHtml(unsafe) {
            return (unsafe||"").toString()
                 .replace(/&/g, "&amp;")
                 .replace(/</g, "&lt;")
                 .replace(/>/g, "&gt;")
                 .replace(/"/g, "&quot;")
                 .replace(/'/g, "&#039;");
        }
        
        function formatText(text) {
            if (!text) return "";
            
            // Format links with tooltips
            let formatted = text.replace(/\b(\d{2}(\.\d{1,2})*)\b/g, (match) => {
                const title = codeTitleMap[match] || "";
                return `<a href="#${match}" class="code-link" title="${escapeHtml(title)}">${match}</a>`;
            });
            
            // Format abbreviations
            formatted = formatted.replace(/\(S\)/g, '(<abbr title="Services">S</abbr>)');
            formatted = formatted.replace(/\(ND\)/g, '(<abbr title="Non-durables">ND</abbr>)');
            formatted = formatted.replace(/\(SD\)/g, '(<abbr title="Semi-durables">SD</abbr>)');
            formatted = formatted.replace(/\(D\)/g, '(<abbr title="Durables">D</abbr>)');
            formatted = formatted.replace(/\bn\.e\.c\./g, '<abbr title="Not elsewhere classified">n.e.c.</abbr>');
            
            return formatted;
        }

        function renderContent(data, container, maxLevel) {
            const flatItems = flattenData(data, maxLevel);
            let html = '';
            
            for (const item of flatItems) {
                const level = getLevel(item.code);
                const headingTag = 'h' + Math.min(level + 1, 6);
                
                let titleHtml = formatText(escapeHtml(item.title));
                if (item.tags && item.tags.length > 0) {
                    titleHtml += ' ' + formatText('(' + item.tags.join(', ') + ')');
                }
                
                html += `<div class="content-item" id="${item.code}">`;
                html += `<${headingTag}>${titleHtml}<span class="code">${item.code}</span></${headingTag}>`;
                
                if (item.intro) {
                    html += `<div class="content-description">${formatText(escapeHtml(item.intro))}</div>`;
                }
                
                if (item.includes && item.includes.length > 0) {
                    html += `<details class="collapsible" open><summary class="includes">Includes</summary><ul>`;
                    for (const inc of item.includes) html += `<li>${formatText(escapeHtml(inc))}</li>`;
                    html += `</ul></details>`;
                }

                if (item.alsoIncludes && item.alsoIncludes.length > 0) {
                    html += `<details class="collapsible" open><summary class="includes" style="color: #0277bd;">Also Includes</summary><ul>`;
                    for (const inc of item.alsoIncludes) html += `<li>${formatText(escapeHtml(inc))}</li>`;
                    html += `</ul></details>`;
                }
                
                if (item.excludes && item.excludes.length > 0) {
                    html += `<details class="collapsible" open><summary class="excludes">Excludes</summary><ul>`;
                    for (const exc of item.excludes) html += `<li>${formatText(escapeHtml(exc))}</li>`;
                    html += `</ul></details>`;
                }
                
                html += '</div>';
            }
            
            container.innerHTML = html;
        }
        
        let contentRendered = false;
        let scrollObserver = null;
        
        function render(forceContent = false) {
            const maxLevel = parseInt(document.getElementById('level-select').value);
            renderTOC(coicopData, document.getElementById('toc-container'), maxLevel);
            
            if (!contentRendered || forceContent) {
                renderContent(coicopData, document.getElementById('content-container'), 6); // Always render all content
                contentRendered = true;
                setupScrollspy();
            }
        }
        
        document.getElementById('level-select').addEventListener('change', () => render(false));
        
        function setupScrollspy() {
            if (scrollObserver) scrollObserver.disconnect();
            
            const contentItems = document.querySelectorAll('.content-item');
            
            scrollObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const id = entry.target.id;
                        const tocRows = document.querySelectorAll('.toc-row');
                        tocRows.forEach(row => {
                            row.classList.toggle('active', row.dataset.code === id);
                            
                            // Scroll TOC to active item if needed
                            if (row.dataset.code === id && row.classList.contains('active')) {
                                // Do NOT automatically expand lower levels on scroll
                                // Only scroll the TOC to the active item if it is currently visible
                                const tocItem = row.closest('.toc-item');
                                let isVisible = true;
                                let parentItem = tocItem.parentElement.closest('.toc-item');
                                while (parentItem) {
                                    if (!parentItem.classList.contains('expanded')) {
                                        isVisible = false;
                                        break;
                                    }
                                    parentItem = parentItem.parentElement.closest('.toc-item');
                                }
                                
                                if (isVisible) {
                                    const container = document.getElementById('toc-container');
                                    const rowTop = row.offsetTop;
                                    const containerTop = container.scrollTop;
                                    const containerHeight = container.clientHeight;
                                    
                                    if (rowTop < containerTop || rowTop > containerTop + containerHeight - 50) {
                                        container.scrollTop = rowTop - containerHeight / 2;
                                    }
                                }
                            }
                        });
                    }
                });
            }, { rootMargin: '-20% 0px -70% 0px' });
            
            contentItems.forEach(item => scrollObserver.observe(item));
        }
        
        render(true);
        
        // Handle fragment navigation on load
        window.addEventListener('load', () => {
            if (window.location.hash) {
                const id = window.location.hash.substring(1);
                const target = document.getElementById(id);
                if (target) {
                    setTimeout(() => target.scrollIntoView(), 100);
                }
            }
        });

        // Add smooth scrolling for internal links and expand TOC
        document.addEventListener('click', function(e) {
            let link = e.target.closest('a');
            if (link && link.getAttribute('href') && link.getAttribute('href').startsWith('#')) {
                const id = link.getAttribute('href').substring(1);
                
                // If it's a TOC link, expand it (but not all its children)
                if (link.classList.contains('toc-link')) {
                    const tocItem = link.closest('.toc-item');
                    if (tocItem) {
                        tocItem.classList.add('expanded');
                    }
                }
                
                const target = document.getElementById(id);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth' });
                    history.pushState(null, null, '#' + id);
                }
            }
        });
    </script>
</body>
</html>"""

html_out = html_template.replace("__JSON_DATA__", json_str).replace(
    "__CODE_TITLE_MAP__", code_title_map_json
)

with open("classification.html", "w", encoding="utf-8") as f:
    f.write(html_out)

# Update guide.html with tooltips if needed
try:
    with open("guide.html", "r", encoding="utf-8") as f:
        guide_html = f.read()

    # Check if codeTitleMap is already there, if not add it or update it
    import re

    map_js = f"const codeTitleMap = {code_title_map_json};"

    # Pattern to find or insert the script
    if "const codeTitleMap =" in guide_html:
        guide_html = re.sub(r"const codeTitleMap = \{.*?\};", map_js, guide_html)
    else:
        # Insert before the end of DOMContentLoaded or at the start of script
        insertion = map_js + "\n        "
        guide_html = guide_html.replace(
            "const tocContent =", insertion + "const tocContent ="
        )

    # Add logic to apply tooltips to links in guide.html
    tooltip_logic = """
        // Apply tooltips to COICOP links
        document.querySelectorAll('a[href*="classification.html#"]').forEach(link => {
            const code = link.getAttribute('href').split('#')[1];
            if (codeTitleMap[code]) {
                link.setAttribute('title', codeTitleMap[code]);
            }
        });
    """
    if "// Apply tooltips to COICOP links" not in guide_html:
        guide_html = guide_html.replace(
            "tocContent.innerHTML = tocHTML;",
            "tocContent.innerHTML = tocHTML;" + tooltip_logic,
        )

    with open("guide.html", "w", encoding="utf-8") as f:
        f.write(guide_html)
    print("Updated guide.html with tooltips")
except Exception as e:
    print(f"Could not update guide.html: {e}")

print("Done")
