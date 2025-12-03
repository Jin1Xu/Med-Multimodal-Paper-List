import re
import json
import glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "README.md"

PAPERS_DIR = ROOT / "papers"
START_MARK = "<!-- PAPERS_START -->"
END_MARK = "<!-- PAPERS_END -->"

LUNG_BRAIN_PAPERS_DIR = ROOT / "lung_brain_papers"
LB_START_MARK = "<!-- LB_PAPERS_START -->"
LB_END_MARK = "<!-- LB_PAPERS_END -->"


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


def _load_papers_from_dir(papers_dir: Path):
    """
    从指定目录下读取所有 json 文件，返回:
        dict[(conf, year)] -> [papers...]
    """
    grouped = defaultdict(list)
    papers_dir = Path(papers_dir)

    for path in glob.glob(str(papers_dir / "*.json")):
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
            # 如果论文 json 里有 year/conf 字段就用；否则用文件名解析的
            year = p.get("year") or year_from_file
            conf_key = (p.get("conf") or conf).upper()
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = year_from_file
            grouped[(conf_key, year)].append(p)
            
    return grouped


def load_papers():
    """原有多模态论文列表（papers 目录）"""
    return _load_papers_from_dir(PAPERS_DIR)


def load_lung_brain_papers():
    """肺部和脑部 AI 论文列表（lung_brain_papers 目录）"""
    return _load_papers_from_dir(LUNG_BRAIN_PAPERS_DIR)



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

    # 作者：只保留第一作者
    authors_raw = p.get("author_site") or p.get("author") or ""
    authors_raw = authors_raw.strip()
    if authors_raw:
        tmp = authors_raw.replace(";", ",")
        first_author = tmp.split(",")[0].strip()
        authors = first_author
    else:
        authors = ""

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
    每个 (conf, year) 区块用 <details> 折叠。
    """
    # 每个会议先按 year 降序，再按名称排序
    sorted_keys = sorted(grouped_papers.keys(), key=lambda k: (k[1], k[0]), reverse=True)
    sections = []
    for (conf, year) in sorted_keys:
        papers = grouped_papers[(conf, year)]
        paper_count = len(papers)
        
        #papers = sorted(papers, key=lambda p: int(p["id"]))
        def sort_key(p):
            id_ = str(p["id"])
            try:
                # 优先按数字排序
                return (0, int(id_))
            except ValueError:
                # 不能转数字的，排在后面，再按字符串排序
                return (1, id_)
        papers = sorted(papers, key=sort_key)

        #header = f"### {conf} {year}\n\n共筛选出 {paper_count} 篇论文\n"

        table_header = (
            "| ID | Title | Authors | Status | Citations | AnyCode |\n"
            "| -- | ----- | ------- | :----: | :-------: | :-----: |"
        )

        rows = [paper_to_row(p) for p in papers]
        inner_md = table_header + "\n" + "\n".join(rows)
        section_md = (
            "<details>\n"
            f"  <summary><strong>{conf} {year}</strong>（共筛选出 {paper_count} 篇论文）</summary>\n\n"
            "  <br/>\n\n"
            f"{inner_md}\n"
            "</details>"
        )

        sections.append(section_md)

    return "\n\n".join(sections)


def replace_section(readme_text, new_section, start_mark, end_mark):
    """
    用 new_section 替换 README 中 start_mark 与 end_mark 之间的内容。
    """
    start_idx = readme_text.find(start_mark)
    end_idx = readme_text.find(end_mark)

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        # 若没有标记，则在末尾追加一个完整区块
        block = f"\n\n{start_mark}\n{new_section}\n{end_mark}\n"
        return readme_text + block

    before = readme_text[: start_idx + len(start_mark)]
    after = readme_text[end_idx:]
    return f"{before}\n\n{new_section}\n{after}"


def main():
    grouped_papers = load_papers()
    if grouped_papers:
        grouped_md = build_grouped_markdown(grouped_papers)
    else:
        grouped_md = "_当前没有任何多模态医学论文数据_"

    lung_brain_papers = load_lung_brain_papers()
    if lung_brain_papers:
        lung_brain_md = build_grouped_markdown(lung_brain_papers)
    else:
        lung_brain_md = "_当前没有任何肺部和脑部相关论文数据_"

    if README_PATH.exists():
        readme_text = README_PATH.read_text(encoding="utf-8")
    else:
        readme_text = "# Papers\n"
        
    new_readme = replace_section(readme_text, grouped_md)
    README_PATH.write_text(new_readme, encoding="utf-8")
    print("README.md updated.")

if __name__ == "__main__":
    main()
