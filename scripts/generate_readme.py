import re
import json
import glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = ROOT / "papers"
README_PATH = ROOT / "README.md"

START_MARK = "<!-- PAPERS_START -->"
END_MARK = "<!-- PAPERS_END -->"


def parse_conf_year_from_filename(path: str):
    stem = Path(path).stem 

    # 正则匹配
    m = re.match(r"([A-Za-z]+)(\d+)", stem)
    if m:
        conf = m.group(1).upper()      # 'eccv' -> 'ECCV'
        year = int(m.group(2))         # '2024' -> 2024
    else:
        letters = "".join(ch for ch in stem if ch.isalpha())
        digits = "".join(ch for ch in stem if ch.isdigit())
        conf = letters.upper() if letters else "UNKNOWN_CONF"
        year = int(digits) if digits.isdigit() else 0

    return conf, year


def load_papers():
    """
    输出 dict:
        key: (conf, year)
        value: 该会议该年份的所有论文列表
    """
    grouped = defaultdict(list)
    for path in glob.glob(str(PAPERS_DIR / "*.json")):
        conf, year_from_file = parse_conf_year_from_filename(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            papers = [data]
        elif isinstance(data, list):
            papers = data
        else:
            raise ValueError(f"Unsupported JSON format in {path}")

        # 将每篇论文放入按 (conf, year) 分组的字典中
        for p in papers:
            # 如果论文json里有 year/conf 字段就用；否则用文件名解析的
            year = p.get("year") or year_from_file
            conf_key = (p.get("conf") or conf).upper()

            # year 必须是 int，防御性处理一下
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = year_from_file

            grouped[(conf_key, year)].append(p)

    return grouped


def paper_to_row(p):
    # 论文id
    paper_id = p.get("id")

    # 标题及论文链接
    raw_title = p.get("title", "")
    title_clean = raw_title.strip().strip('"')
    pdf = p.get("pdf") or ""
    arxiv = p.get("arxiv") or ""
    link_target = arxiv or pdf # 优先级arxiv>pdf 
    if link_target:
        title_md = f"[{title_clean}]({link_target})"
    else:
        title_md = title_clean

    # 作者
    authors = p.get("author_site") or p.get("author") or ""
    authors = authors.replace(";", ",")

    # status
    status = p.get("status")

    # 论文引用次数
    citations = p.get("gs_citation", 0)

    # 开源代码
    github_link = p.get("github") or ""
    code = f"[Code😻]({github_link})" if github_link else "😾"
    
    return (f"| {paper_id} | {title_md} | {authors} | {status} | {citations} | {code} | ")


def build_grouped_markdown(grouped_papers):
    """
    输出 grouped_papers: dict[(conf, year)] -> [papers...]
    """
    # 每个会议先按 year 降序，再按名称排序
    sorted_keys = sorted(grouped_papers.keys(), key=lambda k: (k[1], k[0]), reverse=True)
    sections = []
    for (conf, year) in sorted_keys:
        papers = grouped_papers[(conf, year)]

        # 统计该会议该年份的论文数量
        paper_count = len(papers)

        # 按论文 id 的数值大小排序
        papers = sorted(papers, key=lambda p: int(p["id"]))

        header = f"### {conf} {year}\n\n共筛选出 {paper_count} 篇论文\n"
        table_header = (
            "| ID | Title | Authors | Status | Citations | AnyCode |\n"
            "| -- | ----- | ------- | :----: | :-------: | :-----: |"
        )

        rows = [paper_to_row(p) for p in papers]
        section_md = header + table_header + "\n" + "\n".join(rows)
        sections.append(section_md)

    return "\n\n".join(sections)


def replace_section(readme_text, new_section):
    start_idx = readme_text.find(START_MARK)
    end_idx = readme_text.find(END_MARK)

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        # 如果没写标记，就在结尾追加一个新段落
        block = f"\n\n{START_MARK}\n{new_section}\n{END_MARK}\n"
        return readme_text + block

    before = readme_text[: start_idx + len(START_MARK)]
    after = readme_text[end_idx:]
    return f"{before}\n\n{new_section}\n{after}"


def main():
    grouped_papers = load_papers()
    
    if grouped_papers:
        grouped_md = build_grouped_markdown(grouped_papers)
    else:
        grouped_md = "_当前没有任何论文数据_"

    if README_PATH.exists():
        readme_text = README_PATH.read_text(encoding="utf-8")
    else:
        readme_text = "# Papers\n"
        
    new_readme = replace_section(readme_text, grouped_md)
    README_PATH.write_text(new_readme, encoding="utf-8")
    print("README.md updated.")

if __name__ == "__main__":
    main()
