# -*- coding: utf-8 -*-
"""
data_topic.py - Thu thap bai bao theo chu de tu Europe PMC, xuat nodes.csv / relationships.csv cho Neo4j.

Chay:
    py -m pip install requests
    py data_topic.py            # chay that (can mang)
    py data_topic.py --selftest # test offline voi du lieu gia, khong goi API

Dau ra (thu muc out/):
    raw_papers.jsonl       ban ghi goc tu API (de chay lai khong phai tai lai)
    refs_cache.json        cache danh sach tai lieu tham khao cua tung PMID
    papers.csv             bai bao + abstract + MeSH (dung cho buoc phan loai chu de)
    author_mentions.csv    moi lan mot tac gia xuat hien (de gop nguoi trung ten o buoc sau)
    nodes.csv, relationships.csv
"""
import csv
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations

import requests

# ====================== CAU HINH ======================
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
TOPIC_NAME = "mRNA vaccine"
# Truy van: cum tu mRNA vaccine, chi lay ban ghi PubMed/MEDLINE co abstract, 2018 - 2025-06
QUERY = ('("mRNA vaccine" OR "mRNA vaccines" OR "messenger RNA vaccine") '
         'AND SRC:MED AND HAS_ABSTRACT:y AND (FIRST_PDATE:[2018-01-01 TO 2025-06-30])')
MAX_PAPERS = 5000
PAGE_SIZE = 200               # so ban ghi moi trang (cursorMark)
MAX_AUTHORS_FOR_PAIRS = 30    # bai co nhieu tac gia hon nguong nay: khong tao CO_AUTHOR / COLLABORATES_WITH
FETCH_REFS = True             # lay danh sach trich dan (mat ~1 request / bai)
ONLY_MAJOR_MESH = True        # chi lay MeSH major topic lam Topic
SLEEP = 0.25                  # nghi giua cac request (giay)
OUT_DIR = "out"

# ====================== TIEN ICH ======================
def strip_accents(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))

def slug(s):
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)

def http_get(url, params=None, tries=5):
    # goi API co thu lai (backoff)
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            print("HTTP", r.status_code, "- thu lai...")
        except Exception as e:
            print("Loi mang:", e)
        time.sleep(2 ** i)
    return None

# ====================== THU THAP ======================
def fetch_papers():
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "raw_papers.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            recs = [json.loads(l) for l in f if l.strip()]
        if recs:
            print("Dung lai raw_papers.jsonl:", len(recs), "bai (xoa file de tai lai)")
            return recs
    recs, seen, cursor = [], set(), "*"
    while len(recs) < MAX_PAPERS:
        data = http_get(BASE + "/search", {
            "query": QUERY, "format": "json", "resultType": "core",
            "pageSize": PAGE_SIZE, "cursorMark": cursor})
        if not data:
            print("Khong lay duoc trang, dung.")
            break
        items = data.get("resultList", {}).get("result", [])
        if not items:
            break
        for it in items:
            pmid = it.get("pmid")
            if pmid and pmid not in seen and it.get("abstractText"):
                seen.add(pmid)
                recs.append(it)
        print("Da co", len(recs), "bai / tong khop", data.get("hitCount"))
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
        time.sleep(SLEEP)
    recs = recs[:MAX_PAPERS]
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return recs

def save_json_atomic(path, obj):
    # ghi ra file tam roi doi ten, tranh hong file neu may treo giua chung
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def load_json_safe(path):
    # doc cache; neu file hong thi bo qua va bat dau lai
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Cache hong (", e, ") -> bo qua, lay lai tu dau")
        return {}

def fetch_refs(pmids):
    # tra ve dict pmid -> list PMID duoc trich dan (chi nguon MED)
    path = os.path.join(OUT_DIR, "refs_cache.json")
    cache = load_json_safe(path)
    todo = [p for p in pmids if p not in cache]
    print("Trich dan: can lay", len(todo), "bai (da cache", len(cache), ")")
    try:
        for i, pmid in enumerate(todo, 1):
            data = http_get(f"{BASE}/MED/{pmid}/references", {"format": "json", "pageSize": 1000})
            lst = []
            if data:
                for r in data.get("referenceList", {}).get("reference", []):
                    if r.get("source") == "MED":
                        rid = r.get("id") or r.get("pmid")
                        if rid:
                            lst.append(str(rid))
            cache[pmid] = lst
            if i % 50 == 0:
                print("  refs", i, "/", len(todo))
                save_json_atomic(path, cache)
            time.sleep(SLEEP)
    finally:
        # luon luu cache ke ca khi bi Ctrl+C
        save_json_atomic(path, cache)
    return cache

# ====================== PHAN TICH DON VI CONG TAC ======================
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")

TIER_UNI = ("universit", "universidad", "universite", "universitat", "universita", "universidade")
TIER_MED = ("medical corporation", "hospital", "hopital", "klinik", "clinic", "institut", "college", "school of",
            "medical school", "laborator", "center", "centre", "academy", "foundation", "council")
TIER_GOV = ("agency", "ministry", "government", "administration", "authority", "bureau")
DEPT_RE = re.compile(r"^(the )?(department|dept|division|faculty|section|unit|program|programme)\b", re.I)
NOT_CO_RE = re.compile(r"\b(medical|health|hospital|clinic|universit\w*|institut\w*|agency|ministry|"
                       r"government|department|division|college|school)\b", re.I)
NAMED_CO_RE = re.compile(r"\b(pfizer|moderna|biontech|novartis|sanofi|gsk|glaxosmithkline|astrazeneca|merck|"
                         r"janssen|roche|genentech|bayer|curevac|novavax|takeda|abbvie|lilly|amgen|gilead|"
                         r"regeneron|sinovac|sinopharm|cansino|arcturus|gritstone)\b", re.I)

# cong ty: khop theo TU (word boundary) de tranh nham "Agency", "Agriculture", "Rochester"...
CO_RE = re.compile(r"\b(inc|ltd|llc|gmbh|corp|corporation|plc|ag|limited|pharma|pharmaceuticals?|"
                   r"biotech|biotechnology|therapeutics|biosciences)\b|biontech|moderna|pfizer|novavax|curevac",
                   re.I)
PHARMA_RE = re.compile(r"\b(pfizer|moderna|biontech|novartis|sanofi|gsk|glaxosmithkline|astrazeneca|"
                       r"merck|janssen|johnson & johnson|roche|genentech|bayer|curevac|novavax|takeda|"
                       r"abbvie|eli lilly|bristol[- ]myers|amgen|gilead|regeneron|sinovac|sinopharm|"
                       r"cansino|arcturus|gritstone|pharma|pharmaceuticals?|therapeutics)\b", re.I)

COUNTRIES = {
    "usa": "United States", "united states": "United States", "u.s.a": "United States", "us": "United States",
    "uk": "United Kingdom", "united kingdom": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom", "china": "China", "germany": "Germany",
    "france": "France", "italy": "Italy", "spain": "Spain", "japan": "Japan", "canada": "Canada",
    "australia": "Australia", "netherlands": "Netherlands", "the netherlands": "Netherlands",
    "switzerland": "Switzerland", "sweden": "Sweden", "denmark": "Denmark", "norway": "Norway",
    "finland": "Finland", "belgium": "Belgium", "austria": "Austria", "israel": "Israel",
    "india": "India", "brazil": "Brazil", "korea": "South Korea", "south korea": "South Korea",
    "republic of korea": "South Korea", "singapore": "Singapore", "taiwan": "Taiwan",
    "hong kong": "China", "russia": "Russia", "turkey": "Turkey", "iran": "Iran", "egypt": "Egypt",
    "saudi arabia": "Saudi Arabia", "south africa": "South Africa", "mexico": "Mexico",
    "argentina": "Argentina", "chile": "Chile", "poland": "Poland", "portugal": "Portugal",
    "ireland": "Ireland", "greece": "Greece", "czech republic": "Czech Republic", "thailand": "Thailand",
    "vietnam": "Vietnam", "viet nam": "Vietnam", "pakistan": "Pakistan", "malaysia": "Malaysia",
    "new zealand": "New Zealand", "hungary": "Hungary", "belgium.": "Belgium", "colombia": "Colombia",
    "nigeria": "Nigeria", "kenya": "Kenya", "bangladesh": "Bangladesh", "indonesia": "Indonesia",
}
SUFFIX_WORDS = r"(inc|ltd|llc|gmbh|corp|corporation|co|ag|plc|sa|bv|nv|limited|pty|lp)"
SUFFIX_RE = re.compile(r"^" + SUFFIX_WORDS + r"\.?$", re.I)

def org_slug(name):
    # id to chuc: bo hau to cong ty de "Moderna" va "Moderna Inc" thanh cung 1 node
    t = slug(name)
    while True:
        t2 = re.sub(r"\s" + SUFFIX_WORDS + r"$", "", t)
        if t2 == t:
            return t
        t = t2

US_STATE_ZIP = re.compile(r"\b[A-Z]{2}\s*\d{5}\b")

def parse_affiliation(aff):
    """Tu chuoi don vi -> (ten to chuc, loai, quoc gia, email list, is_pharma). Heuristic, can kiem tra tay."""
    aff = aff or ""
    emails = [e.rstrip(".").lower() for e in EMAIL_RE.findall(aff)]
    clean = EMAIL_RE.sub("", aff)
    clean = re.sub(r"Electronic address:?", "", clean, flags=re.I)
    segs = [s.strip(" .;") for s in clean.split(",")]
    segs = [s for s in segs if s]
    if not segs:
        return None
    # gop hau to cong ty (Inc, Ltd, ...) vao doan truoc: "Pfizer, Inc." -> "Pfizer Inc"
    merged = []
    for sg in segs:
        if merged and SUFFIX_RE.match(sg):
            merged[-1] = merged[-1] + " " + sg
        else:
            merged.append(sg)
    segs = merged
    # quoc gia: doan cuoi, hoac bang ma bang My + zip
    country = ""
    last = slug(segs[-1])
    if last in COUNTRIES:
        country = COUNTRIES[last]
    elif US_STATE_ZIP.search(clean):
        country = "United States"
    # chon to chuc theo tung bac uu tien (bo qua doan la khoa/phong ban: "Department of ...")
    org, otype = None, "Other"
    for s_ in segs:
        if any(k in " " + strip_accents(s_).lower() for k in TIER_UNI):
            org, otype = s_, "University"
            break
    if not org:
        for s_ in segs:
            if DEPT_RE.match(s_):
                continue
            low = " " + strip_accents(s_).lower()
            if any(k in low for k in TIER_MED):
                org = s_
                hosp = ("hospital", "hopital", "klinik", "clinic", "medical corporation")
                otype = "Hospital" if any(k in low for k in hosp) else "Institute"
                break
    if not org:
        for s_ in segs:                      # co quan nha nuoc (Agency, Ministry...)
            if DEPT_RE.match(s_):
                continue
            if any(k in " " + strip_accents(s_).lower() for k in TIER_GOV):
                org, otype = s_, "Government"
                break
    if not org:
        for s_ in segs:                      # hang ten cu the truoc (Pfizer, Moderna...)
            if NAMED_CO_RE.search(strip_accents(s_)):
                org, otype = s_, "Company"
                break
    if not org:
        for s_ in segs:                      # sau do moi den tu khoa chung (Inc, Pharma...)
            if DEPT_RE.match(s_) or NOT_CO_RE.search(s_):
                continue
            if CO_RE.search(strip_accents(s_)):
                org, otype = s_, "Company"
                break
    if not org:
        org = segs[0]
    # hang duoc: chi danh dau khi la Company, hoac ten khop danh sach ma KHONG phai dai hoc/benh vien
    is_pharma = (otype == "Company") or (otype not in ("University", "Hospital", "Government") and bool(PHARMA_RE.search(strip_accents(org))))
    if is_pharma and otype != "Company":
        otype = "Company"
    return {"org": org, "type": otype, "country": country, "emails": emails, "pharma": is_pharma}

# ====================== XU LY BAN GHI ======================
def author_affs(a):
    out = []
    det = a.get("authorAffiliationDetailsList", {}).get("authorAffiliation", [])
    for d in det:
        if d.get("affiliation"):
            out.append(d["affiliation"])
    if not out and a.get("affiliation"):
        out.append(a["affiliation"])
    return out

def author_orcid(a):
    ai = a.get("authorId")
    if isinstance(ai, dict) and ai.get("type") == "ORCID":
        m = ORCID_RE.search(ai.get("value", ""))
        if m:
            return m.group(0)
    return ""

def name_key(a):
    last = slug(a.get("lastName") or (a.get("fullName") or "").split(" ")[0])
    ini = (a.get("initials") or (a.get("firstName") or "")[:1] or "")[:1].lower()
    return f"{last}|{ini}"

def build(recs, refs):
    """Tao danh sach node va quan he tu ban ghi goc. Khong goi mang."""
    # --- luot 1: map name_key -> tap ORCID (de gan ORCID duy nhat cho cac lan xuat hien khong co ORCID)
    key2orcids = defaultdict(set)
    for r in recs:
        for a in r.get("authorList", {}).get("author", []):
            o = author_orcid(a)
            if o:
                key2orcids[name_key(a)].add(o)

    nodes = {}          # id -> dict
    rels = Counter()    # (start, end, type) -> weight
    mentions = []       # cho author_mentions.csv
    papers_rows = []
    corpus_pmids = {r["pmid"] for r in recs}
    author_names = defaultdict(Counter)
    author_emails = defaultdict(set)
    author_orcid_of = {}

    def add_node(nid, label, **kw):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label}
        nodes[nid].update({k: v for k, v in kw.items() if v not in (None, "")})

    for r in recs:
        pmid = r["pmid"]
        pid = "P_" + pmid
        year = r.get("pubYear") or r.get("journalInfo", {}).get("yearOfPublication") or ""
        add_node(pid, "Paper", name=r.get("title", ""), pmid=pmid, year=year, doi=r.get("doi", ""))

        # tapta chi
        jt = r.get("journalInfo", {}).get("journal", {}).get("title")
        if jt:
            jid = "J_" + slug(jt).replace(" ", "_")
            add_node(jid, "Journal", name=jt)
            rels[(pid, jid, "PUBLISHED_IN")] += 1

        # chu de (MeSH)
        mesh = []
        for m in r.get("meshHeadingList", {}).get("meshHeading", []):
            d = m.get("descriptorName")
            if not d:
                continue
            mesh.append(d)
            if (not ONLY_MAJOR_MESH) or m.get("majorTopic_YN") == "Y":
                tid = "T_" + slug(d).replace(" ", "_")
                add_node(tid, "Topic", name=d)
                rels[(pid, tid, "HAS_TOPIC")] += 1
        papers_rows.append([pid, pmid, r.get("title", ""), year, r.get("doi", ""),
                            (r.get("abstractText") or "").replace("\n", " "), "; ".join(mesh)])

        # trich dan (chi trong tap du lieu)
        for c in refs.get(pmid, []):
            if c in corpus_pmids and c != pmid:
                rels[(pid, "P_" + c, "CITES")] += 1

        # tac gia
        auths = r.get("authorList", {}).get("author", [])
        n = len(auths)
        ids_in_paper, orgs_in_paper = [], set()
        for pos, a in enumerate(auths):
            nk = name_key(a)
            if nk.startswith("|"):
                continue
            orcid = author_orcid(a)
            if not orcid and len(key2orcids.get(nk, ())) == 1:
                orcid = next(iter(key2orcids[nk]))
            aid = ("A_ORCID_" + orcid) if orcid else ("A_" + nk.replace("|", "_"))
            full = a.get("fullName") or nk
            author_names[aid][full] += 1
            if orcid:
                author_orcid_of[aid] = orcid
            ids_in_paper.append(aid)

            affs = author_affs(a)
            m_orgs, m_emails = [], []
            for aff in affs:
                p = parse_affiliation(aff)
                if not p:
                    continue
                oid = "O_" + org_slug(p["org"]).replace(" ", "_")[:80]
                add_node(oid, "Organization", name=p["org"], org_type=p["type"],
                         is_pharma=str(p["pharma"]).lower())
                rels[(aid, oid, "AFFILIATED_WITH")] += 0  # dem o duoi, moi bai 1 lan
                m_orgs.append(oid)
                orgs_in_paper.add(oid)
                for e in p["emails"]:
                    author_emails[aid].add(e)
                    m_emails.append(e)
                if p["country"]:
                    cid = "C_" + slug(p["country"]).replace(" ", "_")
                    add_node(cid, "Country", name=p["country"])
                    rels[(oid, cid, "LOCATED_IN")] = 1
            for oid in set(m_orgs):
                rels[(aid, oid, "AFFILIATED_WITH")] += 1
            mentions.append([pmid, pos, full, aid, orcid, "|".join(sorted(set(m_orgs))),
                             "|".join(sorted(set(m_emails))), " || ".join(affs)])

        # quan he tac gia - bai
        seen_a = set()
        for pos, aid in enumerate(ids_in_paper):
            if aid in seen_a:
                continue
            seen_a.add(aid)
            rels[(aid, pid, "AUTHOR_OF")] += 1
            if pos == 0:
                rels[(aid, pid, "FIRST_AUTHOR_OF")] += 1
            if pos == n - 1 and n >= 2:
                rels[(aid, pid, "LAST_AUTHOR_OF")] += 1

        # dong tac gia + hop tac to chuc (bo bai qua nhieu tac gia)
        if 2 <= len(seen_a) <= MAX_AUTHORS_FOR_PAIRS:
            for x, y in combinations(sorted(seen_a), 2):
                rels[(x, y, "CO_AUTHOR")] += 1
            for x, y in combinations(sorted(orgs_in_paper), 2):
                rels[(x, y, "COLLABORATES_WITH")] += 1

    # cap nhat thuoc tinh tac gia
    for aid, cnt in author_names.items():
        add_node(aid, "Author", name=cnt.most_common(1)[0][0],
                 orcid=author_orcid_of.get(aid, ""), emails=";".join(sorted(author_emails.get(aid, []))))
    # bo cac canh AFFILIATED_WITH co weight 0 (khong phat sinh)
    rels = {k: v for k, v in rels.items() if v > 0}
    return nodes, rels, mentions, papers_rows

# ====================== XUAT FILE ======================
def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)

def export(nodes, rels, mentions, papers_rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    cols = ["id", "label", "name", "pmid", "year", "doi", "orcid", "emails", "org_type", "is_pharma"]
    write_csv(os.path.join(OUT_DIR, "nodes.csv"), cols,
              [[n.get(c, "") for c in cols] for n in nodes.values()])
    write_csv(os.path.join(OUT_DIR, "relationships.csv"), ["start_id", "end_id", "type", "weight"],
              [[s, e, t, w] for (s, e, t), w in rels.items()])
    write_csv(os.path.join(OUT_DIR, "papers.csv"),
              ["id", "pmid", "title", "year", "doi", "abstract", "mesh_all"], papers_rows)
    write_csv(os.path.join(OUT_DIR, "author_mentions.csv"),
              ["pmid", "position", "full_name", "author_id", "orcid", "org_ids", "emails", "raw_affiliations"],
              mentions)
    by_label = Counter(n["label"] for n in nodes.values())
    by_type = Counter(t for (_, _, t) in rels)
    print("\n=== THONG KE NHANH ===")
    print("Node:", dict(by_label), "tong", len(nodes))
    print("Canh:", dict(by_type), "tong", len(rels))

# ====================== SELFTEST (khong can mang) ======================
def selftest():
    fake = [
        {"pmid": "1", "title": "Paper A", "pubYear": "2021", "doi": "10.1/a", "abstractText": "abc",
         "journalInfo": {"journal": {"title": "Nature"}},
         "meshHeadingList": {"meshHeading": [{"descriptorName": "mRNA Vaccines", "majorTopic_YN": "Y"}]},
         "authorList": {"author": [
             {"fullName": "Smith J", "lastName": "Smith", "initials": "J", "authorId": {"type": "ORCID", "value": "0000-0001-2345-6789"},
              "authorAffiliationDetailsList": {"authorAffiliation": [{"affiliation": "Department of Medicine, Harvard Medical School, Boston, MA 02115, USA. Electronic address: js@harvard.edu."}]}},
             {"fullName": "Tran B", "lastName": "Tran", "initials": "B",
              "authorAffiliationDetailsList": {"authorAffiliation": [{"affiliation": "Moderna Inc, Cambridge, MA, USA."}]}}]}},
        {"pmid": "2", "title": "Paper B", "pubYear": "2022", "abstractText": "xyz",
         "journalInfo": {"journal": {"title": "Nature"}},
         "authorList": {"author": [
             {"fullName": "Smith J", "lastName": "Smith", "initials": "J",
              "affiliation": "Institute of Virology, Charite University Hospital, Berlin, Germany."},
             {"fullName": "Tran B", "lastName": "Tran", "initials": "B"}]}},
    ]
    nodes, rels, mentions, rows = build(fake, {"2": ["1"]})
    os.makedirs(OUT_DIR, exist_ok=True)
    export(nodes, rels, mentions, rows)
    types = {t for (_, _, t) in rels}
    print("Loai quan he xuat hien:", sorted(types))
    assert ("P_2", "P_1", "CITES") in rels
    assert any(k[2] == "CO_AUTHOR" and v == 2 for k, v in rels.items()), "CO_AUTHOR phai co weight 2"
    assert ("A_ORCID_0000-0001-2345-6789", "P_2", "FIRST_AUTHOR_OF") in rels, "gan ORCID cho lan khong co ORCID"
    print("SELFTEST OK")

# ====================== MAIN ======================
def main():
    if "--selftest" in sys.argv:
        return selftest()
    recs = fetch_papers()
    print("So bai:", len(recs))
    refs = {}
    if FETCH_REFS:
        refs = fetch_refs([r["pmid"] for r in recs])
        have = sum(1 for p in refs.values() if p)
        print(f"Bai co it nhat 1 tai lieu tham khao MED: {have}/{len(refs)}")
    nodes, rels, mentions, rows = build(recs, refs)
    export(nodes, rels, mentions, rows)

if __name__ == "__main__":
    main()
