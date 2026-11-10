// ============================================================
// queries.cypher - nap nodes.csv / relationships.csv vao Neo4j
// Buoc 0: copy 2 file CSV vao thu muc "import" cua database Neo4j
//         (Neo4j Desktop: ... > Open folder > Import). Chay tung khoi trong Neo4j Browser.
// ============================================================

// ---------- 1. Rang buoc (tao truoc de MERGE nhanh) ----------
CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (n:Paper) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT author_id IF NOT EXISTS FOR (n:Author) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT org_id IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT journal_id IF NOT EXISTS FOR (n:Journal) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (n:Topic) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT country_id IF NOT EXISTS FOR (n:Country) REQUIRE n.id IS UNIQUE;

// ---------- 2. Nap node (moi nhan 1 lenh) ----------
LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
WITH row WHERE row.label = 'Paper'
MERGE (n:Paper {id: row.id})
SET n.title = row.name, n.pmid = row.pmid, n.doi = row.doi,
    n.year = CASE row.year WHEN '' THEN null ELSE toInteger(row.year) END;

LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
WITH row WHERE row.label = 'Author'
MERGE (n:Author {id: row.id})
SET n.name = row.name, n.orcid = row.orcid, n.emails = row.emails;

LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
WITH row WHERE row.label = 'Organization'
MERGE (n:Organization {id: row.id})
SET n.name = row.name, n.org_type = row.org_type, n.is_pharma = (toLower(trim(row.is_pharma)) = 'true');

LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
WITH row WHERE row.label = 'Journal'
MERGE (n:Journal {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
WITH row WHERE row.label = 'Topic'
MERGE (n:Topic {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
WITH row WHERE row.label = 'Country'
MERGE (n:Country {id: row.id}) SET n.name = row.name;

// ---------- 3. Nap quan he (moi loai 1 lenh; label khop chinh xac de dung index) ----------
LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'AUTHOR_OF'
MATCH (a:Author {id: row.start_id}), (p:Paper {id: row.end_id})
MERGE (a)-[:AUTHOR_OF]->(p);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'FIRST_AUTHOR_OF'
MATCH (a:Author {id: row.start_id}), (p:Paper {id: row.end_id})
MERGE (a)-[:FIRST_AUTHOR_OF]->(p);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'LAST_AUTHOR_OF'
MATCH (a:Author {id: row.start_id}), (p:Paper {id: row.end_id})
MERGE (a)-[:LAST_AUTHOR_OF]->(p);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'CO_AUTHOR'
MATCH (a:Author {id: row.start_id}), (b:Author {id: row.end_id})
MERGE (a)-[r:CO_AUTHOR]->(b) SET r.weight = toInteger(row.weight);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'AFFILIATED_WITH'
MATCH (a:Author {id: row.start_id}), (o:Organization {id: row.end_id})
MERGE (a)-[r:AFFILIATED_WITH]->(o) SET r.weight = toInteger(row.weight);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'COLLABORATES_WITH'
MATCH (a:Organization {id: row.start_id}), (b:Organization {id: row.end_id})
MERGE (a)-[r:COLLABORATES_WITH]->(b) SET r.weight = toInteger(row.weight);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'CITES'
MATCH (a:Paper {id: row.start_id}), (b:Paper {id: row.end_id})
MERGE (a)-[:CITES]->(b);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'PUBLISHED_IN'
MATCH (p:Paper {id: row.start_id}), (j:Journal {id: row.end_id})
MERGE (p)-[:PUBLISHED_IN]->(j);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'HAS_TOPIC'
MATCH (p:Paper {id: row.start_id}), (t:Topic {id: row.end_id})
MERGE (p)-[:HAS_TOPIC]->(t);

LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
WITH row WHERE row.type = 'LOCATED_IN'
MATCH (o:Organization {id: row.start_id}), (c:Country {id: row.end_id})
MERGE (o)-[:LOCATED_IN]->(c);

// ============================================================
// THONG KE MANG
// ============================================================

// 4a. Dem node theo nhan / canh theo loai (de dien bang thong ke vao bao cao)
MATCH (n) RETURN labels(n)[0] AS nhan, count(*) AS so_node ORDER BY so_node DESC;
MATCH ()-[r]->() RETURN type(r) AS loai_quan_he, count(*) AS so_canh ORDER BY so_canh DESC;

// 4b. Top 10 tac gia theo so dong tac gia (bac trong do thi co-author, bo qua huong)
MATCH (a:Author)-[:CO_AUTHOR]-(b:Author)
RETURN a.name AS tac_gia, count(DISTINCT b) AS bac ORDER BY bac DESC LIMIT 10;

// 4c. Phan bo bac (dung ve histogram / kiem tra scale-free)
MATCH (a:Author)
OPTIONAL MATCH (a)-[:CO_AUTHOR]-(b:Author)
WITH a, count(DISTINCT b) AS bac
RETURN bac, count(*) AS so_tac_gia ORDER BY bac;

// 4d. Top to chuc theo so tac gia, va so bai cua cac hang duoc (pharma)
MATCH (o:Organization)<-[:AFFILIATED_WITH]-(a:Author)
RETURN o.name AS to_chuc, o.org_type AS loai, count(DISTINCT a) AS so_tac_gia
ORDER BY so_tac_gia DESC LIMIT 15;

MATCH (o:Organization {is_pharma: true})<-[:AFFILIATED_WITH]-(a:Author)-[:AUTHOR_OF]->(p:Paper)
RETURN o.name AS hang, count(DISTINCT p) AS so_bai ORDER BY so_bai DESC LIMIT 15;

// 4e. Bai duoc trich dan nhieu nhat trong tap du lieu
MATCH (p:Paper)<-[:CITES]-(q:Paper)
RETURN p.title AS bai, count(q) AS so_trich_dan_noi_bo ORDER BY so_trich_dan_noi_bo DESC LIMIT 10;

// ============================================================
// THANH PHAN LIEN THONG + DUONG DI NGAN NHAT (GDS Community)
// LUU Y: toi chua chay thu doan GDS ben duoi. Ten ham/tham so doi theo phien ban GDS,
// hay doi chieu voi tai lieu GDS cua dung phien ban ban cai.
// ============================================================

// 5a. Chieu do thi co-author (vo huong)
CALL gds.graph.project(
  'coauth',
  'Author',
  {CO_AUTHOR: {orientation: 'UNDIRECTED'}}
);

// 5b. Thanh phan lien thong (WCC): thong ke so thanh phan va kich thuoc thanh phan lon nhat
CALL gds.wcc.stream('coauth') YIELD nodeId, componentId
WITH componentId, count(*) AS kich_thuoc
RETURN count(*) AS so_thanh_phan, max(kich_thuoc) AS thanh_phan_lon_nhat;

// 5c. Louvain
CALL gds.louvain.stream('coauth') YIELD nodeId, communityId
WITH communityId, count(*) AS size
RETURN communityId, size ORDER BY size DESC LIMIT 10;

// 5d. All-pairs shortest path: ten procedure thay doi theo phien ban
//     (ban cu: gds.alpha.allShortestPaths.stream; ban moi hon co the khac). Kiem tra bang:
SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'gds' AND name CONTAINS 'allShortestPaths' RETURN name;
// Neu co, goi dang: CALL gds.alpha.allShortestPaths.stream('coauth') YIELD sourceNodeId, targetNodeId, distance
//   RETURN avg(distance) AS do_dai_duong_di_trung_binh, max(distance) AS duong_kinh;
// (voi do thi vai nghin node thi OK; luu y chi tinh cac cap co duong di, tuc cung thanh phan)

// 5e. Phuong an KHONG can GDS: lay mau 300 cap ngau nhien, dung shortestPath chuan cua Cypher
MATCH (a:Author)-[:CO_AUTHOR]-()
WITH DISTINCT a
WITH collect(a) AS ds
WITH ds, size(ds) AS n
UNWIND range(1, 300) AS i
WITH ds[toInteger(rand() * n)] AS x, ds[toInteger(rand() * n)] AS y
WHERE x <> y
MATCH p = shortestPath((x)-[:CO_AUTHOR*..12]-(y))
RETURN count(p) AS so_cap_co_duong, avg(length(p)) AS duong_di_trung_binh_mau, max(length(p)) AS lon_nhat;

// 5f. Don dep do thi chieu khi xong
CALL gds.graph.drop('coauth');
