#!/usr/bin/env python3
"""
VFX Knowledge RAG - 基于 TF-IDF 的知识检索
完全本地运行，不需要网络。
用法:
  python rag.py index                  # 重建索引
  python rag.py search "爆炸核心"      # 语义搜索
  python rag.py search "能量衰减" -k 5 # 搜索前5条
  python rag.py add CARD-TEST.md       # 添加单张卡片
  python rag.py stats                  # 显示统计
"""

import sys, os, re, json, pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

WORKSPACE = Path(__file__).resolve().parent.parent
KNOWLEDGE = WORKSPACE.parent / "knowledge"
DATA_DIR = WORKSPACE / "data"

def get_card_files():
    cards = []
    cards_dir = KNOWLEDGE / "cards"
    if cards_dir.exists():
        for f in sorted(cards_dir.glob("*.md")):
            cards.append(f)
    # 也收集资料卡片
    for src_dir in (KNOWLEDGE / "sources").glob("*"):
        src_md = src_dir / "source.md"
        if src_md.exists():
            cards.append(src_md)
    return cards

def chunk_card(filepath):
    text = filepath.read_text(encoding="utf-8")
    filename = filepath.name
    
    chunks = []
    current_section = ""
    current_content = []
    
    for line in text.split("\n"):
        if line.startswith("## ") and current_content:
            chunks.append({
                "section": current_section,
                "content": "\n".join(current_content).strip(),
                "source": filename
            })
            current_section = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)
    
    if current_content:
        chunks.append({
            "section": current_section,
            "content": "\n".join(current_content).strip(),
            "source": filename
        })
    
    # 切分过长的段落
    result = []
    for chunk in chunks:
        content = chunk["content"]
        if len(content) > 1500:
            paragraphs = content.split("\n\n")
            sub = ""
            for p in paragraphs:
                if len(sub) + len(p) > 1500 and sub:
                    result.append({"section": chunk["section"], "content": sub.strip(), "source": chunk["source"]})
                    sub = p
                else:
                    sub += ("\n\n" if sub else "") + p
            if sub.strip():
                result.append({"section": chunk["section"], "content": sub.strip(), "source": chunk["source"]})
        else:
            result.append(chunk)
    
    return result

def build_index():
    print("收集知识卡片...")
    all_chunks = []
    for card_file in get_card_files():
        chunks = chunk_card(card_file)
        for chunk in chunks:
            all_chunks.append(chunk)
    
    if not all_chunks:
        print("未找到任何知识文件。")
        return
    
    print(f"找到 {len(all_chunks)} 个知识块")
    
    # 构建 TF-IDF 索引
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=50000
    )
    
    documents = [c["content"] for c in all_chunks]
    tfidf_matrix = vectorizer.fit_transform(documents)
    
    # 保存
    index_data = {
        "chunks": all_chunks,
        "vectorizer": vectorizer,
        "matrix": tfidf_matrix
    }
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "rag_index.pkl", "wb") as f:
        pickle.dump(index_data, f)
    
    print(f"索引完成：{len(all_chunks)} 个块，{tfidf_matrix.shape[1]} 维特征")

def load_index():
    index_path = DATA_DIR / "rag_index.pkl"
    if not index_path.exists():
        print("索引不存在，请先运行: python rag.py index")
        return None
    with open(index_path, "rb") as f:
        return pickle.load(f)

def search(query, top_k=5):
    data = load_index()
    if not data:
        return
    
    vectorizer = data["vectorizer"]
    tfidf_matrix = data["matrix"]
    chunks = data["chunks"]
    
    query_vec = vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    print(f"搜索: \"{query}\"  (前 {top_k} 条)\n{'='*60}")
    for i, idx in enumerate(top_indices):
        sim = similarities[idx]
        chunk = chunks[idx]
        print(f"\n[{i+1}] 相似度: {sim:.3f}  来源: {chunk['source']}  段落: {chunk['section']}")
        preview = chunk["content"][:300] + "..." if len(chunk["content"]) > 300 else chunk["content"]
        print(f"    {preview}")
    
    return [(float(similarities[idx]), chunks[idx]) for idx in top_indices]

def show_stats():
    data = load_index()
    if data:
        sources = set(c["source"] for c in data["chunks"])
        print(f"索引状态: {len(data['chunks'])} 个知识块，来自 {len(sources)} 个文件")
        print(f"特征维度: {data['matrix'].shape[1]}")
        print(f"索引文件: {DATA_DIR / 'rag_index.pkl'}")
        print(f"\n卡片来源:")
        for s in sorted(sources):
            count = sum(1 for c in data["chunks"] if c["source"] == s)
            print(f"  {s}: {count} 块")
    else:
        print("索引尚未建立。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python rag.py <command> [args]")
        print("  index          重建索引")
        print("  search <query> 语义搜索")
        print("  stats          显示统计")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == "index":
        build_index()
    elif cmd == "search" and len(sys.argv) >= 3:
        query = sys.argv[2]
        k = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "-k" else 5
        search(query, k)
    elif cmd == "stats":
        show_stats()
    else:
        print(f"未知命令: {cmd}")
