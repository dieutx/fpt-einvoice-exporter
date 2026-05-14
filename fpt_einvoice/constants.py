BASE_URL = "https://portal.einvoice.fpt.com.vn"

LOGIN_ENV_MAP = {
    "mst": "FPT_EINVOICE_MST",
    "username": "FPT_EINVOICE_USERNAME",
    "password": "FPT_EINVOICE_PASSWORD",
}

KNOWN_TYPE_LABELS = {
    "01GTKT": "Hóa đơn giá trị gia tăng",
    "03XKNB": "Phiếu xuất kho kiêm vận chuyển nội bộ",
    "01/MTT": "Hóa đơn GTGT từ máy tính tiền",
    "06HDTM": "Hoá đơn thương mại",
}

PRIMARY_COLUMNS = [
    "type_label",
    "type",
    "idt_local",
    "idt",
    "inc",
    "form",
    "serial",
    "seq",
    "status",
    "status_received",
    "ma_cqthu",
    "stax",
    "sname",
    "btax",
    "bcode",
    "bname",
    "buyer",
    "baddr",
    "bmail",
    "sum",
    "vat",
    "total",
    "curr",
    "exrt",
    "paym",
    "sec",
    "ou",
    "uc",
    "note",
    "minutes_status_sign",
    "code_minutes_sign",
    "budget_relationid",
    "idnumber",
    "passport_number",
    "converted_inv",
]

UI_EXPORT_COLUMNS = [
    ("inc", "ID"),
    ("idt", "Ngày HĐ"),
    ("form", "Mẫu số"),
    ("serial", "Ký hiệu"),
    ("seq", "Số HĐ"),
    ("status", "Trạng thái"),
    ("status_received", "Trạng thái CQT"),
    ("ma_cqthu", "Mã CQT cấp"),
    ("btax", "MST"),
    ("bname", "Tên KH"),
    ("buyer", "Người mua"),
    ("baddr", "Địa chỉ"),
    ("btel", "SĐT người mua"),
    ("idnumber", "CCCD người mua"),
    ("sum", "Tổng tiền"),
    ("vat", "VAT"),
    ("total", "Tổng cộng"),
    ("curr", "Loại tiền"),
    ("exrt", "Tỷ giá"),
    ("sec", "Mã TC"),
    ("bmail", "Email"),
    ("ou", "Đơn vị bán"),
    ("uc", "Người lập"),
    ("ic", "IC"),
    ("adjdes", "Thay thế/Điều chỉnh"),
    ("cde", "Bị thay thế/Bị điều chỉnh"),
    ("business_class", "Phân loại nghiệp vụ"),
    ("dtl_invs_status", "ĐC/TT nhiều HĐ"),
    ("sec_dtl", "Mã bảng kê ĐC/TT"),
    ("canrdt", "Ngày hủy"),
    ("canref", "Số văn bản của HD hủy"),
    ("canrea", "Lý do hủy"),
    ("adjrdt", "Ngày VB"),
    ("adjref", "Số văn bản của HD điều chỉnh"),
    ("adjrea", "Lý do"),
    ("minutes_status_sign", "TT ký biên bản"),
    ("code_minutes_sign", "Mã BB"),
    ("bcode", "Mã KH"),
    ("note", "Ghi chú"),
    ("maildt", "Gửi mail"),
    ("converted_inv", "Chuyển đổi"),
    ("id_batch", "ID gói gửi CQT"),
    ("dt", "Ngày gửi dữ liệu"),
]

INVOICE_STATUS_LABELS = {
    "1": "Chờ cấp số",
    "2": "Chờ duyệt",
    "3": "Đã duyệt",
    "4": "Đã hủy",
    "6": "Chờ phát hành",
    "7": "Đã phát hành",
    "9": "Đã hủy",
}

STATUS_RECEIVED_LABELS = {
    "0": "Chờ gửi CQT",
    "1": "Đã gửi CQT",
    "2": "Gửi CQT lỗi",
    "8": "Kiểm tra hợp lệ",
    "9": "Kiểm tra không hợp lệ",
    "10": "CQT cấp mã",
}

MAIL_STATUS_LABELS = {
    "1": "Đã gửi",
    "2": "Chưa gửi",
}

CONVERTED_INV_LABELS = {
    "1": "Đã chuyển đổi",
    "2": "Chưa chuyển đổi",
}

MINUTES_SIGN_STATUS_LABELS: dict[str, str] = {
    "1": "Người bán đã ký",
    "5": "Hoàn tất",
    "None": "Chưa ký",
    "null": "Chưa ký",
}
