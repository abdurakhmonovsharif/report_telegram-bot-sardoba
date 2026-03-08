from __future__ import annotations

from typing import Any

SUPPORTED_LANGUAGES = {"uz", "ru", "en"}


TRANSLATIONS: dict[str, dict[str, str]] = {
    "choose_language": {
        "uz": "Iltimos, xizmat tilini tanlang.",
        "ru": "Пожалуйста, выберите язык интерфейса.",
        "en": "Please select your interface language.",
    },
    "language_saved": {
        "uz": "Til muvaffaqiyatli saqlandi.",
        "ru": "Язык успешно сохранен.",
        "en": "Language saved successfully.",
    },
    "main_menu": {
        "uz": "Asosiy menyu. Amalni tanlang:",
        "ru": "Главное меню. Выберите действие:",
        "en": "Main menu. Choose an action:",
    },
    "arrival": {
        "uz": "Qabul (Приход)",
        "ru": "Приход",
        "en": "Arrival",
    },
    "transfer": {
        "uz": "Ko'chirish (Перемещение)",
        "ru": "Перемещение",
        "en": "Transfer",
    },
    "change_language": {
        "uz": "Tilni o'zgartirish",
        "ru": "Сменить язык",
        "en": "Change language",
    },
    "select_branch": {
        "uz": "Filialni tanlang:",
        "ru": "Выберите филиал:",
        "en": "Select a branch:",
    },
    "select_warehouse": {
        "uz": "Omborni tanlang:",
        "ru": "Выберите склад:",
        "en": "Select a warehouse:",
    },
    "arrival_photo_prompt": {
        "uz": "Nakladnoy rasmlarini yuboring. Tugatganda tugmani bosing yoki \"Nakladnoy yo'q\" ni tanlang.",
        "ru": "Отправьте фото накладной. После загрузки нажмите завершить или выберите \"Накладной нет\".",
        "en": "Upload invoice photos. Press finish when done or choose \"No invoice photo\".",
    },
    "arrival_photo_done": {
        "uz": "Yuklangan rasmlar soni: {count}",
        "ru": "Загружено фото: {count}",
        "en": "Uploaded photos: {count}",
    },
    "arrival_no_photo": {
        "uz": "Nakladnoy mavjud emas",
        "ru": "Накладной нет",
        "en": "No invoice photo",
    },
    "finish_upload": {
        "uz": "Yuklashni tugatish",
        "ru": "Завершить загрузку",
        "en": "Finish upload",
    },
    "manual_text_prompt": {
        "uz": "Mahsulotlar nomi va umumiy narxni matn ko'rinishida yozing.",
        "ru": "Введите названия товаров и общую сумму вручную.",
        "en": "Enter product names and total price manually.",
    },
    "supplier_prompt": {
        "uz": "Yetkazib beruvchini kiriting:",
        "ru": "Введите поставщика:",
        "en": "Enter supplier name:",
    },
    "date_prompt": {
        "uz": "Sanani kiriting (YYYY-MM-DD):",
        "ru": "Введите дату (YYYY-MM-DD):",
        "en": "Enter date (YYYY-MM-DD):",
    },
    "date_invalid": {
        "uz": "Sana noto'g'ri. Format: YYYY-MM-DD",
        "ru": "Неверный формат даты. Используйте YYYY-MM-DD",
        "en": "Invalid date format. Use YYYY-MM-DD",
    },
    "comment_prompt": {
        "uz": "Ko'chirilgan mahsulotlar haqida izoh yozing:",
        "ru": "Введите комментарий о перемещенных товарах:",
        "en": "Write a comment about moved products:",
    },
    "transfer_photo_prompt": {
        "uz": "Rasm yuborish ixtiyoriy. Rasm yuboring yoki o'tkazib yuboring.",
        "ru": "Фото необязательно. Загрузите фото или пропустите.",
        "en": "Photos are optional. Upload photos or skip.",
    },
    "skip_photos": {
        "uz": "Rasmsiz davom etish",
        "ru": "Пропустить фото",
        "en": "Skip photos",
    },
    "request_success": {
        "uz": "So'rov qabul qilindi va guruhga yuborildi. ID: {request_id}",
        "ru": "Заявка сохранена и отправлена в группу. ID: {request_id}",
        "en": "Request saved and sent to the group. ID: {request_id}",
    },
    "request_saved_but_not_sent": {
        "uz": "So'rov saqlandi, lekin guruhga yuborilmadi. Administratorga xabar berildi.",
        "ru": "Заявка сохранена, но не отправлена в группу. Администратор уведомлен.",
        "en": "Request saved, but delivery to the group failed. Administrator was notified.",
    },
    "upload_photo_or_finish": {
        "uz": "Iltimos, rasm yuboring yoki tugatish tugmasini bosing.",
        "ru": "Отправьте фото или нажмите завершить.",
        "en": "Upload a photo or press finish.",
    },
    "safe_error": {
        "uz": "Server xatosi yuz berdi. Iltimos, keyinroq urinib ko'ring.",
        "ru": "Произошла серверная ошибка. Попробуйте позже.",
        "en": "A server error occurred. Please try again later.",
    },
    "cancel": {
        "uz": "Bekor qilish",
        "ru": "Отмена",
        "en": "Cancel",
    },
    "cancelled": {
        "uz": "Amal bekor qilindi.",
        "ru": "Операция отменена.",
        "en": "Operation cancelled.",
    },
    "use_buttons": {
        "uz": "Iltimos, tugmalardan foydalaning.",
        "ru": "Пожалуйста, используйте кнопки.",
        "en": "Please use the buttons.",
    },
}


def t(key: str, lang: str, **kwargs: Any) -> str:
    selected = lang if lang in SUPPORTED_LANGUAGES else "uz"
    text = TRANSLATIONS.get(key, {}).get(selected) or TRANSLATIONS.get(key, {}).get("uz") or key
    if kwargs:
        return text.format(**kwargs)
    return text

