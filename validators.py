import re


UA_MOBILE_CODES = {
    "039", "050", "063", "066", "067", "068",
    "073", "091", "092", "093", "094",
    "095", "096", "097", "098", "099",
}


def digits_only(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def normalize_phone(value: str) -> str:
    digits = digits_only(value)

    if digits.startswith("380") and len(digits) == 12:
        return "+" + digits

    if digits.startswith("0") and len(digits) == 10:
        return "+38" + digits

    return digits


def is_valid_ua_phone(value: str) -> bool:
    phone = normalize_phone(value)

    if not re.fullmatch(r"\+380\d{9}", phone):
        return False

    operator_code = phone[3:6]
    return operator_code in UA_MOBILE_CODES


def is_valid_phone(value: str) -> bool:
    return is_valid_ua_phone(value)


def format_phone(value: str) -> str:
    phone = normalize_phone(value)

    if len(phone) == 13 and phone.startswith("+380"):
        return f"{phone[:4]} {phone[4:6]} {phone[6:9]} {phone[9:11]} {phone[11:]}"

    return phone
