# -*- coding: utf-8 -*-
"""
pharma_papers.py - Dem so bai bao theo to chuc (hang duoc / doanh nghiep) tu out/author_mentions.csv.
Moi bai chi duoc dem 1 lan cho moi to chuc, dua tren tung lan xuat hien cua tac gia trong bai
(khong di qua node tac gia da bi gop, nen khong bi phong to boi cac ten nhu "Wang Y").

Chay:  python pharma_papers.py
"""
import csv
from collections import defaultdict

TOP = 15

# doc danh sach to chuc va co doanh nghiep tu nodes.csv
orgs = {}
with open("out/nodes.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["label"] == "Organization":
            orgs[r["id"]] = (r["name"], r["is_pharma"] == "true", r["org_type"])

# moi to chuc -> tap PMID (moi bai dem 1 lan)
papers = defaultdict(set)
authors = defaultdict(set)
with open("out/author_mentions.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        for oid in filter(None, r["org_ids"].split("|")):
            papers[oid].add(r["pmid"])
            authors[oid].add(r["author_id"])

rows = []
for oid, pm in papers.items():
    name, is_pharma, otype = orgs.get(oid, (oid, False, ""))
    rows.append((len(pm), len(authors[oid]), name, is_pharma, otype))
rows.sort(reverse=True)

print("=== Top doanh nghiep (is_pharma) theo so bai ===")
for n_papers, n_auth, name, ph, ot in [r for r in rows if r[3]][:TOP]:
    print(f"{n_papers:5d} bai | {n_auth:4d} tac gia | {name}")

print("\n=== Top to chuc (moi loai) theo so bai ===")
for n_papers, n_auth, name, ph, ot in rows[:TOP]:
    print(f"{n_papers:5d} bai | {n_auth:4d} tac gia | {ot:10s} | {name}")

# luu file de dua vao bao cao
with open("out/org_paper_counts.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["org_name", "org_type", "is_pharma", "so_bai", "so_tac_gia"])
    for n_papers, n_auth, name, ph, ot in rows:
        w.writerow([name, ot, ph, n_papers, n_auth])
print("\nDa luu out/org_paper_counts.csv")
