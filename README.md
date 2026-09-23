# FPT eInvoice Exporter

Tải hóa đơn từ FPT eInvoice và xuất Excel theo tháng hoặc năm, giữ định dạng cột và cách chuyển đổi dữ liệu của giao diện FPT.

## 1. Cài đặt

Dùng Python 3.11+ và chạy các lệnh sau trong terminal:

```bash
git clone https://github.com/dieutx/fpt-einvoice-exporter.git
cd fpt-einvoice-exporter
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Các lệnh bên dưới chạy tại thư mục repo, sau khi kích hoạt `.venv`.

## 2. Cấu hình đăng nhập

Tạo file `.env` tại thư mục repo, điền thông tin thật thay cho các giá trị mẫu:

```dotenv
FPT_EINVOICE_MST=<MA_SO_THUE>
FPT_EINVOICE_USERNAME=<TEN_DANG_NHAP>
FPT_EINVOICE_TOKEN=<TOKEN_HIEN_TAI>
```

Có token: tool gọi API trực tiếp, bỏ qua browser login. Khi token hết hạn, cập nhật `.env` rồi chạy lại lệnh export.

<details>
<summary>Đăng nhập bằng mật khẩu nếu chưa có token</summary>

Bỏ dòng `FPT_EINVOICE_TOKEN` khỏi `.env`, thêm mật khẩu:

```dotenv
FPT_EINVOICE_PASSWORD=<MAT_KHAU>
```

Sau đó chạy:

```bash
fpt-einvoice-exporter login --headed
```

Hoàn thành reCAPTCHA nếu được yêu cầu. Session được lưu tại `profiles/default/fpt_session.json` để dùng cho các lần export sau.

</details>

## 3. Tải hóa đơn cả năm

```bash
fpt-einvoice-exporter export-year --year 2022 --resume
fpt-einvoice-exporter export-year --year 2023 --resume
```

Mỗi lệnh chạy tháng 01 → 12, chia mỗi tháng thành **01–10, 11–20, 21–cuối tháng**, rồi tạo một file Excel cho tháng đó. Tháng không có hóa đơn vẫn tạo file với header.

Mặc định của `export-year`:

| Thiết lập | Giá trị |
| --- | --- |
| Page tải đồng thời | 5 |
| Số hóa đơn/request | 5.000 |
| Retry mỗi request | 3 lần, chờ 2 giây/lần |
| Số lần thử mỗi khoảng ngày | Tối đa 3 lần, gồm lần đầu |
| Resume | Bật |
| Tự giảm workers/page-size khi lỗi | Tắt |

Muốn chỉ định rõ các tham số:

```bash
fpt-einvoice-exporter export-year --year 2023 \
  --workers 5 --page-size 5000 \
  --max-retries 3 --retry-delay 2 --range-retries 3 \
  --no-adaptive-page-size --resume
```

**Sau Ctrl+C hoặc lỗi API:** chạy lại cùng lệnh, giữ nguyên thư mục output, loại hóa đơn và page-size. Giữ các file raw/checkpoint để tool tiếp tục từ những page đã lưu.

## 4. Gom Excel theo năm

```bash
fpt-einvoice-exporter merge-year --year 2022
fpt-einvoice-exporter merge-year --year 2023
```

Kết quả: `output/fpt_einvoice_2023_all_months.xlsx`, mỗi tháng một sheet tên `2023-01` … `2023-12`. Tool ưu tiên đọc raw JSONL để gom nhanh; nếu không có raw thì đọc sheet `invoices_all` trong Excel tháng.

Thiếu tháng sẽ báo lỗi. Dùng `--skip-missing` nếu chỉ muốn gom các tháng đã có:

```bash
fpt-einvoice-exporter merge-year --year 2023 --skip-missing
```

## File kết quả nằm ở đâu?

```text
output/
├── 2023-02/
│   ├── parts/                     # Checkpoint của 3 khoảng ngày
│   │   ├── 01_10/
│   │   ├── 11_20/
│   │   └── 21_END/
│   ├── raw/                       # JSONL đã gom theo tháng
│   ├── metadata.json
│   └── fpt_einvoice_2023-02.xlsx
└── fpt_einvoice_2023_all_months.xlsx
```

Excel tháng có 3 sheet: `metadata` (thông tin lần chạy), `summary` (số lượng theo loại), `invoices_all` (dữ liệu hóa đơn). Excel năm chỉ chứa các sheet tháng. Mỗi sheet tối đa 1.048.575 dòng dữ liệu, cộng một dòng header.

## Tải riêng một khoảng ngày

```bash
fpt-einvoice-exporter export \
  --from-date 2023-02-01 --to-date 2023-02-10 \
  --output-dir output/custom-2023-02-01_10 \
  --workers 5 --page-size 5000 --no-adaptive-page-size --resume
```

Lệnh `export` dùng nguyên khoảng ngày được nhập; với dữ liệu lớn, nên chọn khoảng ngắn. `export-year` tự chia tháng và dùng luồng ghi Excel streaming.

Mặc định `--types all-known` hỗ trợ `01GTKT`, `03XKNB`, `01/MTT`, `06HDTM`. Để chọn loại cụ thể, thêm `--types '01GTKT,01/MTT'`.

## Tra cứu và phát triển

```bash
fpt-einvoice-exporter export-year --help
fpt-einvoice-exporter merge-year --help
python -m unittest discover -v
```

Cũng có thể thay `fpt-einvoice-exporter` bằng `python fpt_einvoice_exporter.py`. Schema và chuyển đổi dữ liệu nằm trong `UI_EXPORT_COLUMNS` (`constants.py`) và `build_ui_export_row()` (`export.py`).

**Bảo mật:** giữ `.env`, session/token, log và dữ liệu hóa đơn trên máy; không commit hoặc chia sẻ chúng. File `.env.example` chỉ chứa giá trị mẫu.
