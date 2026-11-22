#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval3/score.py —— 三臂实验评分器

用法：python score.py <臂名> <输出文件> [臂名2 输出文件2 ...]
地面真值：cases/ground_truth.json（由独立标注代理产出）

评分口径（事先写定，不事后调）：
  · 主口径 = 案例级（id 级）：一个案例算"真问题"还是"不是"
  · 辅口径 = (id, 类型) 级：类型也算一条
  · UNCLEAR 不算 FP 也不算 TP，单列"双方都判不清"的重合度
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(text):
    """从臂的输出里抽机器可读块。"""
    findings, unclear = [], []
    count = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^FINDING\|([^|]+)\|([^|]*)\|(.*)$", line)
        if m:
            findings.append({"id": m.group(1).strip(), "type": m.group(2).strip(),
                             "desc": m.group(3).strip()})
            continue
        m = re.match(r"^UNCLEAR\|([^|]+)\|(.*)$", line)
        if m:
            unclear.append({"id": m.group(1).strip(), "desc": m.group(2).strip()})
            continue
        m = re.match(r"^COUNT\|(\d+)", line)
        if m:
            count = int(m.group(1))
    return findings, unclear, count


GT_PATH = os.environ.get("GT", os.path.join(HERE, "cases", "ground_truth.json"))


def load_gt():
    p = GT_PATH
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def score(arm, path, gt):
    text = open(path, encoding="utf-8").read()
    f, u, c = parse(text)
    gt_find = {x["id"] for x in gt["findings"]}
    gt_unclear = {x["id"] for x in gt.get("unclear", [])}
    gt_types = {(x["id"], x["type"]) for x in gt["findings"]}

    arm_ids = {x["id"] for x in f}
    arm_types = {(x["id"], x["type"]) for x in f}

    tp = sorted(arm_ids & gt_find)
    fp = sorted(arm_ids - gt_find - gt_unclear)
    fn = sorted(gt_find - arm_ids)
    both_unclear = sorted({x["id"] for x in u} & gt_unclear)
    # 双方都判不清的：臂报了 UNCLEAR，GT 也标 UNCLEAR
    fp_on_unclear = sorted((arm_ids & gt_unclear) - gt_find)

    prec = len(tp) / len(arm_ids) if arm_ids else 0.0
    rec = len(tp) / len(gt_find) if gt_find else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    # 辅口径
    tp_t = len(arm_types & gt_types)
    prec_t = tp_t / len(arm_types) if arm_types else 0.0
    rec_t = tp_t / len(gt_types) if gt_types else 0.0
    f1_t = 2 * prec_t * rec_t / (prec_t + rec_t) if (prec_t + rec_t) else 0.0

    return {
        "arm": arm,
        "n_findings": len(f), "n_ids": len(arm_ids), "count_line": c,
        "tp": tp, "fp": fp, "fn": fn,
        "both_unclear": both_unclear, "fp_on_unclear": fp_on_unclear,
        "precision": prec, "recall": rec, "f1": f1,
        "type_precision": prec_t, "type_recall": rec_t, "type_f1": f1_t,
        "uncLEAR_reported": sorted({x["id"] for x in u}),
    }


def main(argv):
    gt = load_gt()
    if gt is None:
        print("缺 cases/ground_truth.json")
        return 2
    rows = []
    for i in range(1, len(argv), 2):
        arm, path = argv[i], argv[i + 1]
        if not os.path.exists(path):
            print("缺文件：%s" % path)
            continue
        rows.append(score(arm, path, gt))

    gt_n = len({x["id"] for x in gt["findings"]})
    print("=" * 76)
    print("地面真值：%d 个案例判为真问题，%d 个判为引文无法判定" %
          (gt_n, len(gt.get("unclear", []))))
    print("=" * 76)
    hdr = ("臂", "报出", "COUNT", "TP", "FP", "FN", "精确率", "召回率", "F1", "类型F1")
    print("%-14s %5s %6s %4s %4s %4s %8s %8s %6s %8s" % hdr)
    for r in rows:
        print("%-14s %5d %6s %4d %4d %4d %7.0f%% %7.0f%% %5.0f%% %7.0f%%" % (
            r["arm"], r["n_ids"], r["count_line"], len(r["tp"]), len(r["fp"]),
            len(r["fn"]), r["precision"] * 100, r["recall"] * 100, r["f1"] * 100,
            r["type_f1"] * 100))
    print()
    for r in rows:
        print("── %s" % r["arm"])
        print("   命中 : %s" % (", ".join(r["tp"]) or "无"))
        print("   误报 : %s" % (", ".join(r["fp"]) or "无"))
        print("   漏掉 : %s" % (", ".join(r["fn"]) or "无"))
        if r["fp_on_unclear"]:
            print("   报在'无法判定'上 : %s" % ", ".join(r["fp_on_unclear"]))
        if r["both_unclear"]:
            print("   双方都判不清 : %s" % ", ".join(r["both_unclear"]))
        print()
    json.dump(rows, open(os.path.join(HERE, os.environ.get("OUT", "scores.json")), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("已写出 scores.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
