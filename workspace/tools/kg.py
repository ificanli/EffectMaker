#!/usr/bin/env python3
"""
VFX Knowledge Graph - 知识关系图谱
用 NetworkX 管理知识卡片、规则、实验之间的关系。
用法:
  python kg.py build              # 从知识卡片构建图谱
  python kg.py show               # 显示图谱统计
  python kg.py related "爆炸核心"  # 查找相关规则
  python kg.py export             # 导出为 JSON
"""

import sys, re, json
from pathlib import Path

try:
    import networkx as nx
except ImportError:
    print("需要安装 networkx: pip install networkx")
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parent.parent
KNOWLEDGE = WORKSPACE.parent / "knowledge"
DATA_DIR = WORKSPACE / "data"

def extract_rules_from_card(filepath):
    """从知识卡片提取规则节点"""
    text = filepath.read_text(encoding="utf-8")
    filename = filepath.name
    
    rules = []
    current_rule = None
    
    for line in text.split("\n"):
        # 检测规则标题 (### N. 标题)
        match = re.match(r'^###\s+\d+\.\s+(.+)', line)
        if match:
            if current_rule:
                rules.append(current_rule)
            current_rule = {
                "id": f"{filename}__{match.group(1)[:30]}",
                "name": match.group(1),
                "source": filename,
                "evidence": [],
                "keywords": set()
            }
        elif current_rule:
            # 提取证据时间戳
            timestamps = re.findall(r'`(\d{2}:\d{2}:\d{2}[–-]\d{2}:\d{2}:\d{2})`', line)
            if timestamps:
                current_rule["evidence"].extend(timestamps)
            # 提取关键词
            for kw in ["爆炸", "衰减", "冰", "水", "火", "雷电", "刀光", "接触", "核心",
                       "颜色", "亮度", "球罩", "空间", "包裹", "掩体", "原型",
                       "粒子", "alpha", "Alpha", "Fresnel", "Shader"]:
                if kw in line:
                    current_rule["keywords"].add(kw)
    
    if current_rule:
        rules.append(current_rule)
    
    return rules

def extract_card_metadata(filepath):
    """提取卡片元数据"""
    text = filepath.read_text(encoding="utf-8")
    filename = filepath.name
    
    meta = {
        "id": filename,
        "pipeline": "unknown",
        "status": "unknown",
        "verification": "unknown"
    }
    
    for line in text.split("\n"):
        if "管道" in line and "审美" in line:
            meta["pipeline"] = "aesthetic"
        elif "管道" in line and "制作" in line:
            meta["pipeline"] = "craft"
        elif "状态：`experimental`" in line:
            meta["status"] = "experimental"
        elif "状态：`verified`" in line:
            meta["status"] = "verified"
        elif "状态：`adopted`" in line:
            meta["status"] = "adopted"
        elif "single-source" in line:
            meta["verification"] = "single-source"
        elif "cross-verified" in line:
            meta["verification"] = "cross-verified"
        elif "experiment-backed" in line:
            meta["verification"] = "experiment-backed"
    
    return meta

def build_graph():
    """从知识卡片构建图谱"""
    G = nx.DiGraph()
    
    cards_dir = KNOWLEDGE / "cards"
    if not cards_dir.exists():
        print("未找到知识卡片目录")
        return
    
    all_rules = []
    all_meta = []
    
    for card_file in sorted(cards_dir.glob("*.md")):
        meta = extract_card_metadata(card_file)
        all_meta.append(meta)
        
        # 添加卡片节点
        G.add_node(card_file.stem, type="card", **meta)
        
        # 提取规则
        rules = extract_rules_from_card(card_file)
        all_rules.extend(rules)
        
        for rule in rules:
            G.add_node(rule["id"], type="rule", name=rule["name"])
            G.add_edge(card_file.stem, rule["id"], relation="contains")
    
    # 自动发现规则间的关系（共享关键词）
    for i, r1 in enumerate(all_rules):
        for j, r2 in enumerate(all_rules):
            if i >= j:
                continue
            shared_kws = r1["keywords"] & r2["keywords"]
            if len(shared_kws) >= 2:
                G.add_edge(r1["id"], r2["id"], 
                          relation="related",
                          shared_keywords=list(shared_kws))
    
    # 保存为 JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    graph_data = {
        "nodes": [{"id": n, **{k: str(v) if isinstance(v, list) else v for k, v in d.items()}} for n, d in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, **{k: str(v) if isinstance(v, list) else v for k, v in d.items()}} for u, v, d in G.edges(data=True)]
    }
    with open(DATA_DIR / "knowledge_graph.json", "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    
    # 统计
    card_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "card"]
    rule_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "rule"]
    related_edges = [(u,v) for u,v,d in G.edges(data=True) if d.get("relation") == "related"]
    
    print(f"图谱构建完成:")
    print(f"  卡片节点: {len(card_nodes)}")
    print(f"  规则节点: {len(rule_nodes)}")
    print(f"  规则关联: {len(related_edges)}")
    print(f"  文件: {DATA_DIR / 'knowledge_graph.json'}")
    
    return G

def find_related(query):
    """查找与查询相关的规则"""
    G = load_graph()
    if not G:
        return
    
    rule_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get("type") == "rule"]
    
    # 简单关键词匹配
    matches = []
    query_lower = query.lower()
    for node_id, data in rule_nodes:
        name = data.get("name", "")
        if any(kw in name for kw in query_lower.split()):
            matches.append((node_id, data))
    
    if not matches:
        # 尝试部分匹配
        for node_id, data in rule_nodes:
            name = data.get("name", "")
            for kw in query_lower.split():
                if len(kw) > 1 and kw in name:
                    matches.append((node_id, data))
                    break
    
    if not matches:
        print(f"未找到匹配: \"{query}\"")
        return
    
    print(f"与 \"{query}\" 相关的规则:\n{'='*50}")
    for node_id, data in matches:
        print(f"\n  {data.get('name', '?')}")
        print(f"    来源: {G.nodes[node_id].get('source', '?') if 'source' in G.nodes[node_id] else '?'}")
        
        # 查找关联规则
        related = []
        for _, target, edge_data in G.out_edges(node_id, data=True):
            if edge_data.get("relation") == "related":
                target_data = G.nodes.get(target, {})
                if target_data.get("name"):
                    shared = edge_data.get("shared_keywords", [])
                    related.append(f"{target_data['name']} [{','.join(shared)}]")
        
        if related:
            print(f"    关联规则:")
            for r in related:
                print(f"      - {r}")

def load_graph():
    graph_path = DATA_DIR / "knowledge_graph.json"
    if not graph_path.exists():
        print("图谱不存在，请先运行: python kg.py build")
        return None
    with open(graph_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    G = nx.DiGraph()
    for node in data.get("nodes", []):
        node_id = node.pop("id")
        G.add_node(node_id, **node)
    for edge in data.get("edges", []):
        source = edge.pop("source")
        target = edge.pop("target")
        G.add_edge(source, target, **edge)
    return G

def show_stats():
    G = load_graph()
    if not G:
        return
    
    card_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "card"]
    rule_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "rule"]
    related_edges = [(u,v) for u,v,d in G.edges(data=True) if d.get("relation") == "related"]
    
    print(f"知识图谱统计:")
    print(f"  总节点: {G.number_of_nodes()}")
    print(f"  卡片: {len(card_nodes)}")
    print(f"  规则: {len(rule_nodes)}")
    print(f"  规则关联: {len(related_edges)}")
    print(f"  总边数: {G.number_of_edges()}")
    
    if rule_nodes:
        # 找连接最多的规则（最通用的规则）
        in_degree = G.in_degree()
        top_rules = sorted([(n, in_degree[n]) for n in rule_nodes], key=lambda x: -x[1])[:5]
        print(f"\n  最常关联的规则:")
        for node, degree in top_rules:
            if degree > 0:
                name = G.nodes[node].get("name", "?")
                print(f"    {name} ({degree} 条关联)")

def export_json():
    """导出为 JSON"""
    G = load_graph()
    if not G:
        return
    
    data = {
        "nodes": [{"id": n, **d} for n, d in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)]
    }
    
    out_path = DATA_DIR / "knowledge_graph.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"导出完成: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python kg.py <command> [args]")
        print("  build           构建图谱")
        print("  show            显示统计")
        print("  related <query> 查找相关规则")
        print("  export          导出JSON")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == "build":
        build_graph()
    elif cmd == "show":
        show_stats()
    elif cmd == "related" and len(sys.argv) >= 3:
        find_related(" ".join(sys.argv[2:]))
    elif cmd == "export":
        export_json()
    else:
        print(f"未知命令: {cmd}")
