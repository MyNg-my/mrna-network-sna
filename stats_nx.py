# -*- coding: utf-8 -*-
"""
stats_nx.py - Thong ke do thi dong tac gia + do duong di ngan nhat trung binh (chinh xac) bang NetworkX.
Chay:  py -m pip install networkx
       py stats_nx.py
"""
import csv
import math
import time
import networkx as nx

G = nx.Graph()
with open("out/relationships.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["type"] == "CO_AUTHOR":
            G.add_edge(r["start_id"], r["end_id"], weight=int(r["weight"]))

print("Node:", G.number_of_nodes(), " Canh:", G.number_of_edges())
comps = sorted(nx.connected_components(G), key=len, reverse=True)
print("So thanh phan lien thong:", len(comps), " Lon nhat:", len(comps[0]))

H = G.subgraph(comps[0]).copy()          # thanh phan lien thong lon nhat
n, m = H.number_of_nodes(), H.number_of_edges()
degs = [d for _, d in H.degree()]
k_avg = sum(degs) / n
print(f"Bac TB: {k_avg:.2f}, bac max: {max(degs)}")

# duong di ngan nhat TB giua moi cap (BFS tu moi nut; O(n*(n+m)), vai nghin nut van chay duoc)
t0 = time.time()
tong, so_cap, diam = 0, 0, 0
for s, dist in nx.all_pairs_shortest_path_length(H):
    for t, d in dist.items():
        if s < t:                         # moi cap tinh 1 lan
            tong += d
            so_cap += 1
            diam = max(diam, d)
L = tong / so_cap if so_cap else float("nan")
print(f"Duong di ngan nhat TB L = {L:.3f}, duong kinh = {diam}, thoi gian {time.time() - t0:.1f}s")

# so sanh voi do thi ngau nhien cung n, k: L_rand ~ ln(n)/ln(k), C_rand ~ k/n
C = nx.average_clustering(H)
if k_avg > 1:
    L_rand = math.log(n) / math.log(k_avg)
    C_rand = k_avg / n
    print(f"Clustering C = {C:.3f}  | ngau nhien: L ~ {L_rand:.2f}, C ~ {C_rand:.4f}")
    print("Small-world neu L gan L_rand va C >> C_rand")
