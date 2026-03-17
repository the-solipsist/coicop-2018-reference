import re


def process_text_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Remove form feed characters (page breaks)
    text = text.replace("\x0c", "")

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if re.match(r"^\s*\d+\s*$", line):
            continue
        if (
            "Classification of Individual Consumption According to Purpose (COICOP) 2018"
            in line
        ):
            continue
        if line.strip() == "Part One":
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Pre-process A. \n\n Overview ... because of weird pdf extraction
    text = re.sub(r"^([A-Z]\.)\s*\n+([A-Z][^\n]+)$", r"\1 \2", text, flags=re.MULTILINE)

    # Process headings
    text = re.sub(r"^([I|V|X]+\.\s+.+)$", r"\n<h2>\1</h2>\n", text, flags=re.MULTILINE)
    text = re.sub(r"^([A-Z]\.\s+.+)$", r"\n<h3>\1</h3>\n", text, flags=re.MULTILINE)
    text = re.sub(r"^(\d+\.\s+.+)$", r"\n<h4>\1</h4>\n", text, flags=re.MULTILINE)

    blocks = re.split(r"\n\s*\n", text)
    processed_blocks = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        if block.startswith("<h"):
            processed_blocks.append(block)
            continue

        if re.search(r"^\s*[-•]\s+", block, flags=re.MULTILINE) or re.search(
            r"^\s*\([a-z]\)\s+", block, flags=re.MULTILINE
        ):
            block_lines = block.split("\n")
            healed_block = ""
            for line in block_lines:
                if re.match(r"^\s*[-•]\s+", line) or re.match(
                    r"^\s*\([a-z]\)\s+", line
                ):
                    if healed_block:
                        healed_block += "<br>\n"
                    healed_block += line
                else:
                    healed_block += " " + line.strip()

            processed_blocks.append(
                f'<p class="guide-text list-text">{healed_block}</p>'
            )
            continue

        if "Table " in block:
            block = block.replace("\n", "<br>\n")
            processed_blocks.append(f'<div class="guide-table">{block}</div>')
        else:
            block = re.sub(r"(?<!<br>)\n(?!\s*<)", " ", block)
            processed_blocks.append(f'<p class="guide-text">{block}</p>')

    return "\n\n".join(processed_blocks)


html_content = process_text_file("intro_extract.txt")
with open("guide_content.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Processed text into guide_content.html")
