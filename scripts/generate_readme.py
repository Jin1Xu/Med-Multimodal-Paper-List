import re
import json
import glob
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# ----------------- 路径与标记常量 -----------------
ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "README.md"

PAPERS_DIR = ROOT / "mm_med_papers"
START_MARK = "<!-- PAPERS_START -->"
END_MARK = "<!-- PAPERS_END -->"

LUNG_BRAIN_PAPERS_DIR = ROOT / "lung_brain_papers"
LB_START_MARK = "<!-- LB_PAPERS_START -->"
LB_END_MARK = "<!-- LB_PAPERS_END -->"

MM_CLASS_PAPERS_DIR = ROOT / "Mm_classification_papers"
MM_CLASS_START_MARK = "<!-- MM_CLASS_PAPERS_START -->"
MM_CLASS_END_MARK = "<!-- MM_CLASS_PAPERS_END -->"

# 每个区块统一用配置来描述，方便扩展与开关
SECTIONS = [
    {
        "dir": PAPERS_DIR,
        "start": START_MARK,
        "end": END_MARK,
        "empty_msg": "_当前没有任何多模态医学论文数据_",
        "enabled": True, 
    },
    {
        "dir": LUNG_BRAIN_PAPERS_DIR,
        "start": LB_START_MARK,
        "end": LB_END_MARK,
        "empty_msg": "_当前没有任何肺部和脑部相关论文数据_",
        "enabled": True,
    },
    {
        "dir": MM_CLASS_PAPERS_DIR,
        "start": MM_CLASS_START_MARK,
        "end": MM_CLASS_END_MARK,
        "empty_msg": "_当前没有任何多模态分类相关论文数据_",
        "enabled": True,
    },
]

# ----------------- 基础工具函数 -----------------
def parse_conf_year_from_filename(path: str) -> Tuple[str, int]:
    """从文件名中解析 (conf, year)，例如: 'nips2025_filtered.json' -> ('NIPS', 2025)"""
    stem = Path(path).stem

    # 正则匹配: 字母 + 数字
    m = re.match(r"([A-Za-z]+)(\d+)", stem)
    if m:
        conf = m.group(1).upper()
        year = int(m.group(2))
    else:
        # 兜底：把所有字母与数字分别取出
        letters = "".join(ch for ch in stem if ch.isalpha())
        digits = "".join(ch for ch in stem if ch.isdigit())
        conf = letters.upper() if letters else "UNKNOWN_CONF"
        year = int(digits) if digits.isdigit() else 0

    return conf, year

def load_grouped_papers(papers_dir: Path) -> Dict[Tuple[str, int], List[Dict[str, Any]]]:
    """
    从指定目录下读取所有 json 文件，返回:
        dict[(conf, year)] -> [paper_dict, ...]
    """
    grouped: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
    papers_dir = Path(papers_dir)

    for path in glob.glob(str(papers_dir / "*.json")):
        conf_from_file, year_from_file = parse_conf_year_from_filename(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 支持 json 为单个 dict 或 list[dict]
        if isinstance(data, dict):
            papers = [data]
        elif isinstance(data, list):
            papers = data
        else:
            raise ValueError(f"Unsupported JSON format in {path}")

        for p in papers:
            # 优先使用 json 中的 year/conf 字段，否则 fallback 到文件名解析结果
            year = p.get("year") or year_from_file
            conf = (p.get("conf") or conf_from_file).upper()
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = year_from_file

            grouped[(conf, year)].append(p)

    return grouped

# ----------------- Markdown 生成相关 -----------------
def paper_to_row(p: Dict[str, Any]) -> str:
    """单篇论文转为 Markdown 表格的一行"""

    # 论文 id
    paper_id = p.get("id", "")

    # 标题及链接（优先级：arxiv > pdf > site）
    raw_title = p.get("title", "") or ""
    title_clean = raw_title.strip().strip('"')
    pdf = p.get("pdf") or ""
    arxiv = p.get("arxiv") or ""
    site = p.get("site") or ""
    link_target = arxiv or pdf or site
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

    # 状态
    status = p.get("status", "") or ""

    # 引用次数（负数或非法视为无）
    citations = p.get("gs_citation", -1)
    if isinstance(citations, (int, float)) and citations >= 0:
        citations_str = str(citations)
    else:
        citations_str = ""

    # 代码链接
    github_link = p.get("github") or ""
    code = f"[Code😻]({github_link})" if github_link else "😾"

    return f"| {paper_id} | {title_md} | {authors} | {status} | {citations_str} | {code} | "


def build_grouped_markdown(grouped_papers: Dict[Tuple[str, int], List[Dict[str, Any]]]) -> str:
    """
    将 grouped_papers: dict[(conf, year)] -> [papers...]
    转为带 <details> 折叠块的 Markdown 字符串。
    """
    # 键按 (year 降序, conf 名称) 排序
    sorted_keys = sorted(grouped_papers.keys(), key=lambda k: (k[1], k[0]), reverse=True)

    sections: List[str] = []
    for conf, year in sorted_keys:
        papers = grouped_papers[(conf, year)]
        paper_count = len(papers)

        # 先按 id 排，再按 title 排；没有 id 的放后面
        def sort_key(p: Dict[str, Any]):
            raw_id = p.get("id")
            if raw_id is None:
                return (2, p.get("title", ""))
            id_str = str(raw_id)
            try:
                return (0, int(id_str))
            except ValueError:
                return (1, id_str)

        papers_sorted = sorted(papers, key=sort_key)

        table_header = (
            "| ID | Title | Authors | Status | Citations | AnyCode |\n"
            "| -- | ----- | ------- | :----: | :-------: | :-----: |"
        )
        rows = [paper_to_row(p) for p in papers_sorted]
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


def replace_section(readme_text: str, new_section: str, start_mark: str, end_mark: str) -> str:
    """
    用 new_section 替换 README 中 start_mark 与 end_mark 之间的内容。
    如果 README 中不存在对应标记，则在末尾追加一个完整区块。
    注意：new_section 可以是空字符串，这样两标记之间就会是空的。
    """
    start_idx = readme_text.find(start_mark)
    end_idx = readme_text.find(end_mark)

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        block = f"\n\n{start_mark}\n{new_section}\n{end_mark}\n"
        return readme_text + block

    before = readme_text[: start_idx + len(start_mark)]
    after = readme_text[end_idx:]
    return f"{before}\n\n{new_section}\n{after}"


# ----------------- 主流程 -----------------
def update_readme() -> None:
    """根据各目录的论文 json 更新 README 中相应区块"""
    if README_PATH.exists():
        readme_text = README_PATH.read_text(encoding="utf-8")
    else:
        readme_text = "# Papers\n"

    for cfg in SECTIONS:
        papers_dir: Path = cfg["dir"]
        start_mark: str = cfg["start"]
        end_mark: str = cfg["end"]
        empty_msg: str = cfg["empty_msg"]
        enabled: bool = cfg.get("enabled", True)

        if not enabled:
            new_section = ""
        else:
            grouped = load_grouped_papers(papers_dir)
            if grouped:
                new_section = build_grouped_markdown(grouped)
            else:
                new_section = empty_msg

        readme_text = replace_section(readme_text, new_section, start_mark, end_mark)

    README_PATH.write_text(readme_text, encoding="utf-8")


def main():
    update_readme()


if __name__ == "__main__":
    main()
