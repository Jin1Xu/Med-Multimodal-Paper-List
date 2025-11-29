import json
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = ROOT / "papers"
README_PATH = ROOT / "README.md"

START_MARK = "<!-- PAPERS_START -->"
END_MARK = "<!-- PAPERS_END -->"


def load_papers():
    papers = []
    for path in glob.glob(str(PAPERS_DIR / "*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 每个文件可能是单个对象或对象列表
            if isinstance(data, dict):
                papers.append(data)
            elif isinstance(data, list):
                papers.extend(data)
            else:
                raise ValueError(f"Unsupported JSON format in {path}")
    return papers


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

    # 论文引用次数
    citations = p.get("gs_citation", 0)

    # 开源代码
    github_link = p.get("github") or ""
    code = f"[Code😺]({github_link})"
    
    return (f"| {paper_id} | {title_md} | {authors} | {citations} | {code} | ")

def build_table(papers):
    #papers = sorted(papers, key=lambda x: x.get("year", 0), reverse=True) # 按年份逆序排序
    
    header = (
        "|  ID   | Title | Authors | Citations | AnyCode |\n"
        "| ----- | ----- | ------- | --------- | ------- |"
    )
    
    rows = [paper_to_row(p) for p in papers]
    return "\n".join([header] + rows)


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
    papers = load_papers()
    table_md = build_table(papers)

    if README_PATH.exists():
        readme_text = README_PATH.read_text(encoding="utf-8")
    else:
        readme_text = "# Papers\n"

    new_readme = replace_section(readme_text, table_md)
    README_PATH.write_text(new_readme, encoding="utf-8")
    print("README.md updated.")


if __name__ == "__main__":
    main()
