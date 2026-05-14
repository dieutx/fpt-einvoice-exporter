# FPT eInvoice Exporter

CLI Python để đăng nhập `portal.einvoice.fpt.com.vn`, lấy bearer token từ session web, gọi API tra cứu hóa đơn và xuất workbook Excel theo khoảng ngày.

## Tính năng

- Đăng nhập FPT eInvoice bằng CloakBrowser với profile có thể tái sử dụng.
- Đọc credential từ `.env`, biến môi trường hoặc tham số CLI.
- Query hóa đơn theo khoảng ngày và loại hóa đơn.
- Lưu raw JSON theo từng loại hóa đơn để đối soát/debug.
- Có thể resume từ raw JSON đã lưu để không tải lại các page đã hoàn tất.
- Có thể tiếp tục khi một loại hóa đơn lỗi và vẫn xuất workbook cho các loại thành công.
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
├── pyproject.toml             # Metadata package và console script
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
git clone https://github.com/dieutx/fpt-einvoice-exporter.git
cd fpt-einvoice-exporter
python3 -m venv .venv
. .venv/bin/activate
pip install .
fpt-einvoice-exporter init
```

Sửa file `.env` vừa được tạo:

```bash
FPT_EINVOICE_MST=<YOUR_MST>
FPT_EINVOICE_USERNAME=<YOUR_USERNAME>
FPT_EINVOICE_PASSWORD=<YOUR_PASSWORD>
```

Kiểm tra môi trường và đăng nhập lần đầu:

```bash
fpt-einvoice-exporter doctor
fpt-einvoice-exporter login --headed
```

Nếu portal yêu cầu reCAPTCHA, tick thủ công trong browser đang mở. Sau khi login thành công, token được lưu trong `profiles/default/fpt_session.json` để các lần export sau không cần mở browser lại.

## Chạy export

Luồng khuyến nghị:

```bash
fpt-einvoice-exporter export \
  --from-date 2026-05-01 \
  --to-date 2026-05-12
```

Xem các loại hóa đơn tài khoản đang có:

```bash
fpt-einvoice-exporter types
```

Nếu export lớn bị lỗi giữa chừng, chạy lại cùng khoảng ngày và thêm resume:

```bash
fpt-einvoice-exporter export \
  --from-date 2026-05-01 \
  --to-date 2026-05-12 \
  --resume
```

Lệnh cũ vẫn dùng được:

```bash
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
| `--max-retries` | Số lần retry cho lỗi API transient `429/5xx`, mặc định `3`. |
| `--retry-delay` | Số giây chờ giữa các lần retry API, mặc định `2.0`. |
| `--resume` | Tiếp tục từ raw JSON đã có trong `output/raw`, bỏ qua các page đã lưu. |
| `--continue-on-error` | Nếu một loại hóa đơn lỗi, vẫn ghi workbook cho các loại thành công và lưu lỗi vào metadata. |
| `--profile-dir` | Thư mục lưu profile CloakBrowser để tái sử dụng session. |
| `--output-dir` | Thư mục chứa Excel, metadata và raw JSON. |
| `--output-name` | Tên file Excel tùy chỉnh. Nếu bỏ qua sẽ tự sinh theo khoảng ngày. |
| `--headed` | Mở browser có giao diện thay vì headless. |
| `--login-wait-seconds` | Số giây chờ nút Đăng nhập sẵn sàng. Tăng giá trị này khi cần tick reCAPTCHA thủ công với `--headed`. |
| `--session-file` | File cache session/bearer token, mặc định `<profile-dir>/fpt_session.json`. |
| `--reuse-token` | Dùng bearer token cache trước khi mở browser đăng nhập. Đây là mặc định. |
| `--no-reuse-token` | Bỏ qua token cache và đăng nhập lại bằng browser. |

## Commands

| Command | Mục đích |
| --- | --- |
| `init` | Tạo `.env` mẫu và thư mục runtime. |
| `doctor` | Kiểm tra Python, dependency, credential, quyền ghi thư mục và session cache. |
| `login --headed` | Đăng nhập portal, xử lý reCAPTCHA thủ công nếu có, lưu session cache. |
| `types` | In danh sách loại hóa đơn đọc từ session cache. |
| `export` | Export hóa đơn ra Excel. |

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

Nếu chạy với `--continue-on-error`, kết quả và `metadata.json` có thêm `errors` theo mã loại hóa đơn. Khi có lỗi bị bỏ qua, trường `ok` là `false` để báo đây là file xuất một phần.

## Cách hoạt động

Script không bấm nút “Tải về” trên portal. Flow hiện tại:

1. Mở portal bằng CloakBrowser với profile chỉ định.
2. Nếu profile chưa có session, tự điền MST, tài khoản, mật khẩu và đăng nhập.
3. Đọc `sessionStorage.session` để lấy bearer token.
4. Gọi API `/api/sea` theo từng loại hóa đơn và từng page.
5. Lưu raw JSON sau mỗi page thành công để có thể resume.
6. Chuẩn hóa dữ liệu và ghi workbook Excel bằng `openpyxl`.

Cách này ổn định hơn cho batch lớn và dễ mở rộng để chạy cron hoặc pipeline nội bộ.

Mặc định CLI lưu session/token vào `<profile-dir>/fpt_session.json` sau lần đăng nhập thành công. Các lần chạy sau sẽ đọc token cache trước và gọi API luôn, tránh mở lại browser/reCAPTCHA. Nếu API trả `401/403` khi dùng token cache, CLI sẽ xóa cache và yêu cầu chạy lại để đăng nhập mới. Nếu muốn ép đăng nhập lại, chạy với `--no-reuse-token` hoặc xóa file session cache.

Khi export lớn bị gián đoạn, chạy lại cùng `--output-dir`, `--types`, khoảng ngày và thêm `--resume`. CLI sẽ đọc các file `output/raw/*.json` đã có, bắt đầu page tiếp theo từ số dòng đã lưu và tiếp tục checkpoint sau mỗi page.

## Phát triển

Chạy test:

```bash
. .venv/bin/activate
python -B -m unittest
```

Test hiện tập trung vào:

- Đọc `.env` và resolve credential.
- Thứ tự cột, format giá trị và sort trong workbook Excel.
- Package structure, console script và wrapper CLI tương thích lệnh cũ.

## Bảo mật dữ liệu

- Không commit `.env`, profile browser, raw JSON, Excel export hoặc dữ liệu hóa đơn thật.
- Không commit file session/token cache như `fpt_session.json`.
- Dùng `--profile-dir` riêng cho từng môi trường/tài khoản nếu cần tách session.
- Khi chia sẻ log lỗi, kiểm tra và xóa MST, username, token, thông tin khách hàng hoặc số hóa đơn nhạy cảm.
