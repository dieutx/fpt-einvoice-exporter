# FPT eInvoice Exporter

CLI Python để đăng nhập `portal.einvoice.fpt.com.vn`, lấy bearer token từ session web, gọi API tra cứu hóa đơn và xuất workbook Excel theo khoảng ngày.

## Tính năng

- Đăng nhập FPT eInvoice bằng CloakBrowser với profile có thể tái sử dụng.
- Đọc credential từ `.env`, biến môi trường hoặc tham số CLI.
- Query hóa đơn theo khoảng ngày và loại hóa đơn.
- Lưu raw JSON theo từng loại hóa đơn để đối soát/debug.
- Xuất Excel gồm `metadata`, `summary`, `invoices_all` và sheet riêng theo từng loại hóa đơn.
- Format cột Excel theo thứ tự gần với màn hình export của web app.

## Cấu trúc repo

```text
.
├── fpt_einvoice/              # Package chính
│   ├── api.py                 # HTTP client, resolve loại hóa đơn, fetch API /api/sea
│   ├── auth.py                # Đăng nhập portal và lấy session token
│   ├── cli.py                 # Parser CLI và flow export chính
│   ├── config.py              # Đọc .env/env vars và validate credential
│   ├── constants.py           # URL, mã loại hóa đơn, mapping trạng thái, schema cột
│   ├── export.py              # Chuẩn hóa dòng hóa đơn và ghi workbook/raw JSON
│   ├── formatting.py          # Format ngày, số, nhãn hiển thị
│   └── log.py                 # Helper log stderr
├── fpt_einvoice_exporter.py   # Wrapper giữ lệnh cũ: python fpt_einvoice_exporter.py
├── tests/                     # Unit tests cho env, schema Excel, package structure
├── .env.example               # Mẫu credential local
├── requirements.txt           # Runtime dependencies
└── README.md
```

Các thư mục runtime như `output/`, `profiles/`, file `.env`, `.xlsx`, `.json` không được commit theo `.gitignore`.

## Yêu cầu

- Python 3.9+
- Linux/macOS có thể chạy CloakBrowser
- Tài khoản FPT eInvoice hợp lệ

Dependency chính:

```text
cloakbrowser==0.3.28
httpx>=0.28.0
openpyxl>=3.1.5
```

Repo này không vendor source CloakBrowser. Package được cài từ `requirements.txt` và script import qua `from cloakbrowser import launch_persistent_context`. Version `0.3.28` đang được pin vì đã test thực tế với portal FPT, nơi có load Google reCAPTCHA.

## Cài đặt

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Sửa `.env`:

```bash
FPT_EINVOICE_MST=<YOUR_MST>
FPT_EINVOICE_USERNAME=<YOUR_USERNAME>
FPT_EINVOICE_PASSWORD=<YOUR_PASSWORD>
```

## Chạy export

Lệnh tương thích cũ:

```bash
. .venv/bin/activate
python fpt_einvoice_exporter.py \
  --from-date 2026-05-01 \
  --to-date 2026-05-12 \
  --types all-known \
  --profile-dir ./profiles/demo \
  --output-dir ./output/demo
```

Có thể chạy qua package:

```bash
python -m fpt_einvoice \
  --from-date 2026-05-01 \
  --to-date 2026-05-12 \
  --types all-known \
  --profile-dir ./profiles/demo \
  --output-dir ./output/demo
```

Override credential tạm bằng env vars:

```bash
FPT_EINVOICE_MST=<YOUR_MST> \
FPT_EINVOICE_USERNAME=<YOUR_USERNAME> \
FPT_EINVOICE_PASSWORD='<YOUR_PASSWORD>' \
python fpt_einvoice_exporter.py \
  --from-date 2026-05-01 \
  --to-date 2026-05-12 \
  --types all-known \
  --profile-dir ./profiles/demo \
  --output-dir ./output/demo
```

## Tham số CLI

| Tham số | Mô tả |
| --- | --- |
| `--mst` | Mã số thuế đăng nhập. Nếu bỏ qua sẽ đọc `FPT_EINVOICE_MST`. |
| `--username` | Username đăng nhập. Nếu bỏ qua sẽ đọc `FPT_EINVOICE_USERNAME`. |
| `--password` | Mật khẩu. Nếu bỏ qua sẽ đọc `FPT_EINVOICE_PASSWORD`. |
| `--env-file` | File `.env` chứa credential, mặc định `./.env`. |
| `--from-date` | Ngày bắt đầu, dạng `YYYY-MM-DD` hoặc `DD/MM/YYYY`. |
| `--to-date` | Ngày kết thúc, dạng `YYYY-MM-DD` hoặc `DD/MM/YYYY`. |
| `--types` | `all-known`, `session` hoặc CSV mã loại hóa đơn, ví dụ `01GTKT,03XKNB`. |
| `--unl` | Giá trị `unl` gửi lên API FPT, mặc định `2`. |
| `--page-size` | Số bản ghi mỗi request API, mặc định `2000`. |
| `--profile-dir` | Thư mục lưu profile CloakBrowser để tái sử dụng session. |
| `--output-dir` | Thư mục chứa Excel, metadata và raw JSON. |
| `--output-name` | Tên file Excel tùy chỉnh. Nếu bỏ qua sẽ tự sinh theo khoảng ngày. |
| `--headed` | Mở browser có giao diện thay vì headless. |

Giá trị `--types`:

- `all-known`: query các loại đã biết và loại xuất hiện trong session tài khoản.
- `session`: chỉ query các loại hóa đơn xuất hiện trong session tài khoản.
- CSV thủ công: ví dụ `01GTKT,03XKNB,01/MTT`.

## Output

Với `--output-dir ./output/demo`, script tạo:

```text
output/demo/
├── metadata.json
├── raw/
│   ├── 01GTKT.json
│   └── 01_MTT.json
└── fpt_einvoice_2026-05-01_to_2026-05-12.xlsx
```

Workbook Excel gồm:

- `metadata`: thông tin lần chạy, khoảng ngày, loại hóa đơn, số dòng.
- `summary`: tổng số dòng theo từng loại hóa đơn.
- `invoices_all`: tất cả hóa đơn, sort theo ngày hóa đơn rồi ID giảm dần.
- Sheet riêng cho từng loại hóa đơn.

Khi chạy thành công, CLI in JSON kết quả ra stdout, gồm đường dẫn file Excel, thư mục output, `metadata.json`, số dòng theo loại và tổng số dòng.

## Cách hoạt động

Script không bấm nút “Tải về” trên portal. Flow hiện tại:

1. Mở portal bằng CloakBrowser với profile chỉ định.
2. Nếu profile chưa có session, tự điền MST, tài khoản, mật khẩu và đăng nhập.
3. Đọc `sessionStorage.session` để lấy bearer token.
4. Gọi API `/api/sea` theo từng loại hóa đơn và từng page.
5. Lưu raw JSON, chuẩn hóa dữ liệu và ghi workbook Excel bằng `openpyxl`.

Cách này ổn định hơn cho batch lớn và dễ mở rộng để chạy cron hoặc pipeline nội bộ.

## Phát triển

Chạy test:

```bash
. .venv/bin/activate
python -B -m unittest
```

Test hiện tập trung vào:

- Đọc `.env` và resolve credential.
- Thứ tự cột, format giá trị và sort trong workbook Excel.
- Package structure và wrapper CLI tương thích lệnh cũ.

## Bảo mật dữ liệu

- Không commit `.env`, profile browser, raw JSON, Excel export hoặc dữ liệu hóa đơn thật.
- Dùng `--profile-dir` riêng cho từng môi trường/tài khoản nếu cần tách session.
- Khi chia sẻ log lỗi, kiểm tra và xóa MST, username, token, thông tin khách hàng hoặc số hóa đơn nhạy cảm.
