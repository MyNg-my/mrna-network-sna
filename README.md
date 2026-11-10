# Mạng tác giả và tổ chức nghiên cứu vắc-xin mRNA (Europe PMC + Neo4j)

Bài tập lớn môn **Phân tích mạng xã hội**, đề 34: *Mạng lưới các tác giả và tổ chức nghiên cứu Y sinh và Dược học quốc tế*, giai đoạn 1 (thu thập và xử lý dữ liệu, lưu trữ đồ thị).

Dự án thu thập 5000 bài báo về chủ đề **mRNA vaccine** từ Europe PMC (bản ghi PubMed/MEDLINE, 2018-01 đến 2025-06), dựng mạng gồm tác giả, tổ chức, tạp chí, chủ đề, quốc gia với **10 loại quan hệ**, xuất ra CSV và nạp vào **Neo4j**.

## Mục lục

1. [Cấu trúc repository](#1-cấu-trúc-repository)
2. [Dữ liệu đầu ra](#2-dữ-liệu-đầu-ra-google-drive)
3. [Yêu cầu hệ thống](#3-yêu-cầu-hệ-thống)
4. [Cài đặt](#4-cài-đặt)
5. [Cách chạy](#5-cách-chạy)
6. [Cài Neo4j và nạp dữ liệu](#6-cài-neo4j-và-nạp-dữ-liệu)
7. [Kiểm tra kết quả](#7-kiểm-tra-kết-quả)
8. [Mô hình đồ thị](#8-mô-hình-đồ-thị)
9. [Cấu hình trong data_topic.py](#9-cấu-hình-trong-data_topicpy)
10. [Các tệp CSV](#10-các-tệp-csv)
11. [Xử lý sự cố](#11-xử-lý-sự-cố)
12. [Nguồn dữ liệu](#12-nguồn-dữ-liệu)

## 1. Cấu trúc repository

```
.
├── data_topic.py        thu thập từ Europe PMC, chuẩn hóa, xuất CSV
├── pharma_papers.py     đếm số bài theo tổ chức từ author_mentions.csv
├── stats_nx.py          thống kê đồ thị đồng tác giả bằng NetworkX
├── queries.cypher       nạp dữ liệu vào Neo4j và truy vấn thống kê
└── README.md
```

Thư mục `out/` (kết quả chạy) **không nằm trong repository** vì dung lượng lớn, xem mục 2.

## 2. Dữ liệu đầu ra

Toàn bộ thư mục `out/` được lưu trên Google Drive:

**Link:** https://drive.google.com/drive/folders/19Xf58eKbmi9odfwlx6R5RZc-WRIW1xWy

Nội dung thư mục:

| Tệp | Mô tả |
|---|---|
| `raw_papers.jsonl` | 5000 bản ghi gốc tải từ Europe PMC |
| `refs_cache.json` | Danh sách tài liệu tham khảo của từng bài (lưu đệm) |
| `papers.csv` | Bài báo kèm abstract và từ khóa MeSH |
| `author_mentions.csv` | Mỗi lần một tác giả xuất hiện trong một bài, kèm đơn vị, email, ORCID gốc |
| `nodes.csv`, `relationships.csv` | Nút và cạnh đã chuẩn hóa, dùng để nạp Neo4j |
| `org_paper_counts.csv` | Số bài theo tổ chức (sinh bởi `pharma_papers.py`) |

**Cách dùng:**

1. Tải thư mục từ Drive về, đặt tên là `out` và để **cạnh** `data_topic.py` (cùng cấp với các tệp `.py`).
2. Chỉ muốn nạp Neo4j: dùng ngay `nodes.csv` và `relationships.csv`, bỏ qua bước thu thập (mục 6).
3. Muốn chạy lại phần xử lý mà không gọi API: giữ `raw_papers.jsonl` và `refs_cache.json` trong `out/` rồi chạy `python data_topic.py`. Chương trình tự dùng lại hai tệp này, chỉ dựng lại các tệp CSV (khoảng một phút).
4. Muốn thu thập lại từ đầu: xóa `raw_papers.jsonl` và `refs_cache.json` rồi chạy `python data_topic.py`.

## 3. Yêu cầu hệ thống

| Thành phần | Phiên bản đã dùng |
|---|---|
| Hệ điều hành | Windows |
| Python | 3.12 |
| requests | 2.31.0 |
| NetworkX | 3.4.2 |
| Neo4j Desktop | 2.3.1 (DBMS 2026.10.1) |
| Kết nối mạng | Cần khi thu thập từ Europe PMC|

Các phiên bản khác có thể chạy được nhưng chưa được kiểm tra.

## 4. Cài đặt

**Bước 1.** Cài Python 3.12 từ python.org. Khi cài, tick **Add python.exe to PATH** và giữ nguyên mục **pip**.

**Bước 2.** Mở PowerShell hoặc Command Prompt, kiểm tra:

```
python --version
python -m pip --version
```

**Bước 3.** Lấy mã nguồn:

```
git clone https://github.com/MyNg-my/mrna-network-sna
cd mrna-network-sna
```

(hoặc bấm **Code > Download ZIP** trên GitHub rồi giải nén).

**Bước 4.** Cài thư viện:

```
python -m pip install requests networkx
```

**Bước 5.** Kiểm tra:

```
python -c "import requests, networkx; print('OK')"
```

Hiện `OK` là xong.

> Lưu ý: nên dùng cùng một lệnh cho cả cài đặt và chạy (`python -m pip` với `python`). Trên Windows, lệnh `py` có thể trỏ sang một bản Python khác bản đã cài thư viện.

## 5. Cách chạy

### 5.1. Kiểm tra nhanh, không cần mạng

```
python data_topic.py --selftest
```

Cuối kết quả phải có dòng `SELFTEST OK` (chạy trên 2 bài giả).

### 5.2. Thu thập và xuất CSV

```
python data_topic.py
```

Chương trình thực hiện:

1. Gọi Europe PMC theo truy vấn chủ đề, lấy 5000 bài (phân trang bằng `cursorMark`), lưu `out/raw_papers.jsonl`.
2. Gọi `/MED/{PMID}/references` cho từng bài, lưu `out/refs_cache.json`. Lần chạy đầu mất vài chục phút. Bấm Ctrl+C rồi chạy lại vẫn tiếp tục từ chỗ dở (cứ 50 bài lưu một lần).
3. Chuẩn hóa tác giả, tách tổ chức, dựng nút và cạnh.
4. Xuất `nodes.csv`, `relationships.csv`, `papers.csv`, `author_mentions.csv` vào `out/` và in thống kê nhanh.

### 5.3. Đếm bài theo tổ chức

```
python pharma_papers.py
```

In hai bảng (doanh nghiệp và mọi tổ chức, theo số bài) và lưu `out/org_paper_counts.csv`. Số bài được đếm theo từng lần tác giả xuất hiện trong bài nên không bị phồng bởi các nút tác giả bị gộp nhầm.

### 5.4. Thống kê đồ thị đồng tác giả

```
python stats_nx.py
```

In số nút, số cạnh, số thành phần liên thông, bậc trung bình, đường đi ngắn nhất trung bình L (tính chính xác trên thành phần liên thông lớn nhất) và hệ số phân cụm C. Tệp này chủ yếu dùng cho giai đoạn 2.

## 6. Cài Neo4j và nạp dữ liệu

### 6.1. Cài Neo4j Desktop

1. Tải Neo4j Desktop cho Windows tại https://neo4j.com/download/ và cài như phần mềm thường.
2. Mở Neo4j Desktop, kích hoạt bằng tài khoản miễn phí.
3. Vào **Instances**, tạo instance mới:
   - **Instance name:** ví dụ `mrna-network`.
   - **Neo4j version:** để mặc định.
   - **Database user:** `neo4j`, đặt mật khẩu từ 8 ký tự và ghi nhớ.
4. Bấm **Start** và đợi trạng thái **RUNNING**. Địa chỉ kết nối: `neo4j://127.0.0.1:7687`.

> Nếu Neo4j mở một cửa sổ PowerShell, **không đóng** cửa sổ đó (chỉ thu nhỏ), vì đóng nó có thể làm instance dừng. Muốn tắt thì bấm **Stop** trong Neo4j Desktop.

### 6.2. Đặt tệp CSV vào thư mục import

1. Trên ô instance bấm dấu ba chấm **⋯ > Open > Instance folder**.
2. Trong thư mục đó, tìm thư mục con `import`. Nếu chưa có, tự tạo thư mục mới tên đúng là `import` (chữ thường).
3. Chép `nodes.csv` và `relationships.csv` (từ `out/`) vào thư mục `import`.
4. Kiểm tra thư mục import có bị đổi cấu hình không: **⋯ > Open > neo4j.conf**, tìm dòng `server.directories.import`. Nếu có thì dùng đúng thư mục ghi trong dòng đó.

### 6.3. Chạy thử đọc tệp

Mở **Query** (thanh bên trái), kết nối vào instance bằng user `neo4j` rồi chạy:

```
LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row RETURN row LIMIT 1
```

Ra một dòng dữ liệu là đúng chỗ. Báo lỗi không tìm thấy tệp thì quay lại bước 7.2.

### 6.4. Nạp dữ liệu

Mở `queries.cypher`, dán **từng khối** vào ô Query và chạy theo thứ tự:

1. Mục 1: tạo ràng buộc duy nhất cho 6 loại nút (6 lệnh `CREATE CONSTRAINT`).
2. Mục 2: nạp 6 loại nút.
3. Mục 3: nạp 10 loại quan hệ.

Nạp lại từ đầu thì xóa dữ liệu cũ trước:

```
MATCH (n) DETACH DELETE n;
```

(ràng buộc ở mục 1 giữ nguyên, không cần tạo lại.)

## 7. Kiểm tra kết quả

Đếm nút:

```
MATCH (n) RETURN labels(n)[0] AS nhan, count(*) AS so_node ORDER BY so_node DESC;
```

Đếm cạnh theo loại:

```
MATCH ()-[r]->() RETURN type(r) AS loai_quan_he, count(*) AS so_canh ORDER BY so_canh DESC;
```

Kết quả tham chiếu (bộ dữ liệu 5000 bài):

| Loại nút | Số lượng |
|---|---|
| Paper | 5.000 |
| Author | 28.405 |
| Journal | 1.298 |
| Topic | 1.251 |
| Country | 49 |
| Organization | [điền theo bản nạp cuối] |

| Quan hệ | Số cạnh |
|---|---|
| CO_AUTHOR | 213.936 |
| AUTHOR_OF | 46.756 |
| CITES | 19.552 |
| HAS_TOPIC | 10.015 |
| PUBLISHED_IN | 4.999 |
| FIRST_AUTHOR_OF | 4.997 |
| LAST_AUTHOR_OF | 4.669 |
| AFFILIATED_WITH, COLLABORATES_WITH, LOCATED_IN | [điền theo bản nạp cuối] |

Số tổ chức và ba loại cạnh cuối bảng phụ thuộc luật tách đơn vị công tác nên thay đổi nếu sửa luật.

`queries.cypher` còn có các truy vấn thống kê: top tác giả theo số đồng tác giả, top tổ chức, bài được trích dẫn nhiều nhất, và phần dành cho giai đoạn 2 (thành phần liên thông, Louvain, đường đi ngắn nhất bằng thư viện Graph Data Science, chưa được kiểm tra trong giai đoạn 1).

## 8. Mô hình đồ thị

| Quan hệ | Nguồn dữ liệu |
|---|---|
| AUTHOR_OF | Danh sách tác giả của bài |
| FIRST_AUTHOR_OF | Tác giả đứng đầu danh sách |
| LAST_AUTHOR_OF | Tác giả đứng cuối (bài từ 2 tác giả trở lên) |
| CO_AUTHOR | Hai tác giả cùng một bài; trọng số là số bài chung |
| AFFILIATED_WITH | Đơn vị công tác ghi trong bài |
| COLLABORATES_WITH | Hai tổ chức cùng xuất hiện trong một bài; trọng số là số bài chung |
| CITES | Danh sách tài liệu tham khảo của Europe PMC, chỉ giữ trích dẫn giữa các bài trong tập dữ liệu |
| PUBLISHED_IN | Tạp chí đăng bài |
| HAS_TOPIC | Từ khóa MeSH chính của bài |
| LOCATED_IN | Quốc gia tách từ chuỗi đơn vị công tác |

Bài có hơn 30 tác giả vẫn có cạnh AUTHOR_OF nhưng không sinh CO_AUTHOR và COLLABORATES_WITH.

## 9. Cấu hình trong data_topic.py

Các biến ở đầu tệp:

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `TOPIC_NAME` | Tên chủ đề (chỉ để ghi nhớ) | `mRNA vaccine` |
| `QUERY` | Truy vấn Europe PMC | cụm mRNA vaccine, `SRC:MED`, có abstract, 2018-01-01 đến 2025-06-30 |
| `MAX_PAPERS` | Số bài tối đa | 5000 |
| `PAGE_SIZE` | Số bản ghi mỗi trang | 200 |
| `MAX_AUTHORS_FOR_PAIRS` | Ngưỡng số tác giả để sinh CO_AUTHOR, COLLABORATES_WITH | 30 |
| `FETCH_REFS` | Có lấy danh sách trích dẫn hay không | `True` |
| `ONLY_MAJOR_MESH` | Chỉ lấy MeSH chính làm chủ đề | `True` |
| `SLEEP` | Thời gian nghỉ giữa các yêu cầu (giây) | 0.25 |
| `OUT_DIR` | Thư mục đầu ra | `out` |

Muốn đổi sang chủ đề khác (ví dụ CRISPR trong liệu pháp gen), sửa `QUERY`, xóa `raw_papers.jsonl` và `refs_cache.json` rồi chạy lại.

## 10. Các tệp CSV

| Tệp | Các cột |
|---|---|
| `nodes.csv` | id, label, name, pmid, year, doi, orcid, emails, org_type, is_pharma |
| `relationships.csv` | start_id, end_id, type, weight |
| `papers.csv` | id, pmid, title, year, doi, abstract, mesh_all |
| `author_mentions.csv` | pmid, position, full_name, author_id, orcid, org_ids, emails, raw_affiliations |
| `org_paper_counts.csv` | org_name, org_type, is_pharma, so_bai, so_tac_gia |

Tiền tố của `id` trong `nodes.csv`: `P_` (Paper, theo PMID), `A_` (Author), `O_` (Organization), `J_` (Journal), `T_` (Topic), `C_` (Country). Loại tổ chức (`org_type`): University, Hospital, Institute, Government, Company, Other. Cột `is_pharma` đánh dấu doanh nghiệp (dược, công nghệ sinh học, dịch vụ).

## 11. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `No module named pip` khi dùng `py -m pip` | Lệnh `py` đang trỏ tới bản Python chưa có pip. Dùng `python -m pip install ...`, hoặc chạy `python -m ensurepip --upgrade`. |
| `ModuleNotFoundError: requests` | Chưa cài thư viện cho đúng bản Python. Chạy `python -m pip install requests networkx`. |
| NCBI báo `Access Denied` | Dự án đã dùng Europe PMC thay NCBI E-utilities; không cần xử lý. |
| `JSONDecodeError` khi đọc `refs_cache.json` | Tệp cache bị hỏng (ví dụ máy treo giữa lúc ghi). Bản hiện tại tự bỏ qua cache hỏng; có thể xóa `out/refs_cache.json` rồi chạy lại. |
| Chạy `data_topic.py` bị ngắt giữa chừng | Chạy lại cùng lệnh, chương trình tiếp tục từ dữ liệu đã lưu đệm. |
| Nhiều dòng `HTTP 429` hoặc `HTTP 5xx` | Tăng `SLEEP` (ví dụ 0.5) để giảm tốc độ gọi API. |
| Neo4j báo `Connection to instance failed` | Kiểm tra instance có đang **RUNNING** không; nếu **STOPPED** thì bấm Start. Đừng đóng cửa sổ PowerShell mà Neo4j mở ra. |
| `LOAD CSV` báo không tìm thấy tệp | Tệp chưa nằm đúng thư mục `import` của instance (mục 7.2), hoặc `neo4j.conf` trỏ import sang thư mục khác. |
| Không thấy thư mục `import` | Tự tạo thư mục tên `import` trong thư mục instance (mục 7.2). |
| Truy vấn hãng dược trả về 0 dòng | Nạp lại `nodes.csv` bản mới nhất (lệnh nạp `is_pharma` trong `queries.cypher` đã dùng `trim` và `toLower`). |

## 12. Nguồn dữ liệu

Dữ liệu bài báo lấy từ [Europe PMC REST API](https://europepmc.org/RestfulWebService) (bản ghi PubMed/MEDLINE). Chương trình chỉ dùng cho mục đích học tập; khi sử dụng lại dữ liệu, tham khảo điều khoản sử dụng của Europe PMC và của từng nhà xuất bản.
