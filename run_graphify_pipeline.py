"""
Graphify Pipeline Execution Script for odoo-hr-agents
=====================================================
Executes the full Graphify knowledge graph pipeline following SKILL.md.
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    out_dir = Path("graphify-out")
    out_dir.mkdir(exist_ok=True)
    root_path = Path(".").resolve()

    # Clean previous stale cache in graphify-out/cache if any to avoid WinError 32
    cache_dir = out_dir / "cache"
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
        except Exception:
            pass

    print("=" * 60)
    print("1. Running Graphify Detection...")
    from graphify.detect import detect
    detection = detect(root_path)
    (out_dir / ".graphify_detect.json").write_text(json.dumps(detection, ensure_ascii=False), encoding="utf-8")
    total_files = detection.get("total_files", 0)
    print(f"Total files detected: {total_files}")
    for cat, flist in detection.get("files", {}).items():
        if flist:
            print(f" - {cat}: {len(flist)} files")

    print("=" * 60)
    print("2. Running AST Structural Extraction (parallel=False for Windows stability)...")
    from graphify.extract import collect_files, extract
    code_files = []
    for f in detection.get("files", {}).get("code", []):
        fp = Path(f)
        if fp.is_dir():
            code_files.extend(collect_files(fp))
        else:
            code_files.append(fp)

    # Filter out virtual environments, node_modules, git, claude plugins
    filtered_code = []
    for cf in code_files:
        p_str = str(cf).replace("\\", "/")
        if any(ignore in p_str for ignore in ["/venv/", "/.venv/", "/node_modules/", "/.git/", "/.claude/", "/site-packages/"]):
            continue
        filtered_code.append(cf)

    print(f"Code files to parse: {len(filtered_code)}")
    ast_result = extract(filtered_code, cache_root=root_path, parallel=False)
    (out_dir / ".graphify_ast.json").write_text(json.dumps(ast_result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"AST extracted: {len(ast_result.get('nodes', []))} nodes, {len(ast_result.get('edges', []))} edges")

    print("=" * 60)
    print("3. Merging Extractions...")
    (out_dir / ".graphify_semantic.json").write_text(json.dumps({
        "nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0
    }), encoding="utf-8")

    merged_nodes = list(ast_result.get("nodes", []))
    merged_edges = list(ast_result.get("edges", []))
    merged_hyper = []

    merged = {
        "nodes": merged_nodes,
        "edges": merged_edges,
        "hyperedges": merged_hyper,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    (out_dir / ".graphify_extract.json").write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Total merged: {len(merged_nodes)} nodes, {len(merged_edges)} edges")

    print("=" * 60)
    print("4. Building Knowledge Graph & Community Clustering...")
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.report import generate
    from graphify.export import to_json

    G = build_from_json(merged, root=str(root_path), directed=False)
    if G.number_of_nodes() == 0:
        print("ERROR: Graph is empty.")
        sys.exit(1)

    communities = cluster(G)
    cohesion = score_all(G, communities)
    tokens = {"input": 0, "output": 0}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges across {len(communities)} communities")

    print("=" * 60)
    print("5. Labeling Communities...")
    labels = {}
    for cid, members in communities.items():
        member_labels = [G.nodes[n].get("label", str(n)) for n in members[:5]]
        top_str = ", ".join(member_labels[:3])
        labels[cid] = f"Community {cid}: {top_str}"

    for cid, members in communities.items():
        m_texts = " ".join([str(n) for n in members]).lower()
        if "musleh" in m_texts:
            labels[cid] = "وكيل الإصلاح الذاتي (مصلح - Musleh)"
        elif "laya" in m_texts:
            labels[cid] = "وكيلة التوجيه والفرز (لايا - Laya)"
        elif "telegram" in m_texts or "bot" in m_texts:
            labels[cid] = "واجهة تيليجرام وسراج (Telegram & Seraj)"
        elif "whisper" in m_texts or "voice" in m_texts:
            labels[cid] = "محرك الهمس والتفريغ الصوتي (Whisper STT)"
        elif "leave" in m_texts:
            labels[cid] = "إدارة الإجازات (Leaves Management)"
        elif "attendance" in m_texts:
            labels[cid] = "الحضور والانصراف (Attendance Engine)"
        elif "payroll" in m_texts:
            labels[cid] = "مسيرات الرواتب ومدد (Payroll & WPS)"
        elif "contract" in m_texts:
            labels[cid] = "عقود العمل والأجور (Contracts Service)"
        elif "disciplinary" in m_texts or "warning" in m_texts:
            labels[cid] = "الجزاءات والانضباط ولائحة العمل (Disciplinary)"
        elif "eos" in m_texts:
            labels[cid] = "مكافأة نهاية الخدمة والتسويات (EOS)"
        elif "gr" in m_texts:
            labels[cid] = "المعاملات الحكومية وقوى ومقيم (Gov Relations)"
        elif "analytics" in m_texts:
            labels[cid] = "مؤشرات الأداء وتحليلات نطاقات (KPIs & Analytics)"
        elif "sijil" in m_texts or "audit" in m_texts:
            labels[cid] = "الرقابة وسجل التدقيق الأمني (Sijil Audit)"
        elif "letter" in m_texts:
            labels[cid] = "الخطابات وشهادات التعريف (Official Letters)"
        elif "web" in m_texts or "fastapi" in m_texts:
            labels[cid] = "بوابة الويب والـ REST API (Web Service)"
        elif "test" in m_texts:
            labels[cid] = "منظومة الاختبارات وضمان الجودة (Test Suite)"

    questions = suggest_questions(G, communities, labels)

    wrote = to_json(G, communities, str(out_dir / "graph.json"), community_labels=labels)
    print(f"graph.json written: {wrote}")

    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        tokens,
        str(root_path),
        suggested_questions=questions,
    )
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    (out_dir / ".graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8")

    print("GRAPH_REPORT.md written successfully.")

    print("=" * 60)
    print("6. Exporting Interactive HTML Visualization...")
    try:
        from graphify.export import to_html
        to_html(G, communities, labels, str(out_dir / "graph.html"))
        print("graph.html generated successfully.")
    except Exception as e:
        print(f"HTML export notice: {e}")

    print("=" * 60)
    print("7. Saving Manifest & Cost Record...")
    try:
        cost = {
            "runs": [{
                "date": datetime.now(timezone.utc).isoformat(),
                "input_tokens": 0,
                "output_tokens": 0,
                "files": len(filtered_code),
            }],
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
        (out_dir / "cost.json").write_text(json.dumps(cost, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"Cost tracker notice: {e}")

    print("=" * 60)
    print("🎉 Graphify Knowledge Graph Build Complete!")
    print(f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()} | Communities: {len(communities)}")
    print(f"Artifacts in {out_dir}:")
    print(" - graph.json")
    print(" - GRAPH_REPORT.md")
    print(" - graph.html")
    print("=" * 60)

if __name__ == "__main__":
    main()
