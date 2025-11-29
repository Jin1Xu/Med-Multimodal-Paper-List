import os
import json
import glob
import time
from typing import List, Dict, Any
from openai import OpenAI

from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from loguru import logger

INPUT_DIR = "./源文件"
OUTPUT_DIR = "./筛选后"

# DeepSeek API
client = OpenAI(
    api_key='123',
    base_url="https://api.deepseek.com"
)

MODEL_NAME = "deepseek-chat"

def is_multimodal_medical_paper(title: str, max_retries: int = 3) -> bool:
    
    user_prompt = f"""
    任务：根据【论文标题】判断其是否为多模态或跨模态的医学类研究论文。如果是，输出'是'；如果不是，输出'否'。
    要求：你只能输出'是'或'否'这两个字的其中之一，**禁止输出任何其他内容**。
    论文标题：{title}
    """
    
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是一位严谨的学术助手。"},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
            )
            text = response.choices[0].message.content.strip()

            if not text:
                return False
            first_char = text[0] # 保险起见，只取第一个非空字符判断

            if first_char == "是":
                return True
            elif first_char == "否":
                return False
            else:
                return False # 若模型输出异常内容，认为不是

        except Exception as e:
            logger.warning(f"调用大模型失败（第 {attempt} 次）：{e}")
            if attempt < max_retries:
                time.sleep(1.5 * attempt)  # 重试间隔
            else:
                logger.error("多次重试仍失败，跳过该标题。")
                return False


def load_json_file(path: str) -> Any:
    """读取单个 json 文件并返回 Python 对象。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_file(data: Any, path: str) -> None:
    """将 data 写入 json 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def process_all_json_files(input_dir: str, output_dir: str) -> None:
    """main"""
    os.makedirs(output_dir, exist_ok=True)

    json_pattern = os.path.join(input_dir, "*.json")
    json_files = glob.glob(json_pattern)

    if not json_files:
        logger.warning(f"目录中未找到任何 JSON 文件: {input_dir}")
        return

    logger.info(f"在目录 {input_dir} 下找到 {len(json_files)} 个 JSON 文件。")

    for json_path in json_files:
        file_name = os.path.basename(json_path)
        logger.info(f"\n正在处理文件: {file_name}")

        try:
            data = load_json_file(json_path)
        except Exception as e:
            logger.error(f"读取 JSON 文件失败: {json_path}: {e}")
            continue

        if not isinstance(data, list):
            logger.warning(f"文件 {file_name} 的顶层结构不是列表，跳过。")
            continue

        logger.info(f"文件 {file_name} 中共有 {len(data)} 篇论文。")

        # 收集当前文件中需要判断的论文
        papers_in_file: List[tuple[Dict[str, Any], str]] = []
        for idx, paper in enumerate(data):
            if not isinstance(paper, dict):
                logger.warning(f"第 {idx} 个元素不是对象(dict)，跳过。")
                continue

            title = paper.get("title", "")
            if not title:
                logger.warning(f"第 {idx} 个论文缺少 title 字段或为空，跳过。")
                continue

            paper_with_src = dict(paper)
            paper_with_src["_source_file"] = file_name
            papers_in_file.append((paper_with_src, title))

        if not papers_in_file:
            logger.warning(f"文件 {file_name} 中没有可用于判断的论文，跳过输出。")
            continue

        logger.info(f"文件 {file_name} 中共有 {len(papers_in_file)} 篇待筛选论文，并发调用大模型。")

        selected_papers: List[Dict[str, Any]] = []

        # 并发调用
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_paper = {
                executor.submit(is_multimodal_medical_paper, title): paper
                for paper, title in papers_in_file
            }

            for future in tqdm(
                as_completed(future_to_paper),
                total=len(future_to_paper),
                desc=f"筛选 {file_name}",
            ):
                paper = future_to_paper[future]
                try:
                    is_multi_med = future.result()
                    if is_multi_med:
                        selected_papers.append(paper)
                except Exception as e:
                    logger.error(f"并发任务异常: {e}")

        logger.info(f"文件 {file_name} 共筛选出 {len(selected_papers)} 篇多模态/跨模态医学论文。")

        # 为当前文件写出单独的 filtered json
        base_name, _ = os.path.splitext(file_name)
        output_filename = f"{base_name}_filtered.json"
        output_path = os.path.join(output_dir, output_filename)
        save_json_file(selected_papers, output_path)
        logger.success(f"文件 {file_name} 的筛选结果已写入：{output_path}")
