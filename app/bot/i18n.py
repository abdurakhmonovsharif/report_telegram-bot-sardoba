from __future__ import annotations

from typing import Any

SUPPORTED_LANGUAGES = {"uz", "ru", "en"}


TRANSLATIONS: dict[str, dict[str, str]] = {
    "choose_language": {
        "uz": "Iltimos, xizmat tilini tanlang.",
        "ru": "Пожалуйста, выберите язык интерфейса.",
        "en": "Please select your interface language.",
    },
    "phone_request": {
        "uz": "Davom etish uchun telefon raqamingizni yuboring.",
        "ru": "Для продолжения отправьте свой номер телефона.",
        "en": "Please share your phone number to continue.",
    },
    "share_phone": {
        "uz": "Telefon raqamini yuborish",
        "ru": "Отправить номер телефона",
        "en": "Share phone number",
    },
    "share_own_phone": {
        "uz": "Faqat o'zingizning telefon raqamingizni yuboring.",
        "ru": "Пожалуйста, отправьте только свой номер телефона.",
        "en": "Please share only your own phone number.",
    },
    "phone_saved": {
        "uz": "Telefon raqamingiz saqlandi.",
        "ru": "Ваш номер телефона сохранен.",
        "en": "Your phone number has been saved.",
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
    "start_prompt": {
        "uz": "Davom etish uchun Boshlash tugmasini bosing.",
        "ru": "Для продолжения нажмите кнопку «Запуск».",
        "en": "Press Start to continue.",
    },
    "start_button": {
        "uz": "Boshlash",
        "ru": "Запуск",
        "en": "Start",
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
    "select_transfer_kind": {
        "uz": "Ko'chirish turini tanlang:",
        "ru": "Выберите тип перемещения:",
        "en": "Select transfer type:",
    },
    "transfer_kind_internal": {
        "uz": "Omborlar orasida",
        "ru": "Между складами",
        "en": "Internal transfer",
    },
    "transfer_kind_branch": {
        "uz": "Filiallar orasida",
        "ru": "Между филиалами",
        "en": "Between branches",
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
    "select_source_branch": {
        "uz": "Yuboruvchi filialni tanlang:",
        "ru": "Выберите филиал-отправитель:",
        "en": "Select source branch:",
    },
    "select_destination_branch": {
        "uz": "Qaysi filialga ko'chirilayotganini tanlang:",
        "ru": "Выберите филиал-получатель:",
        "en": "Select destination branch:",
    },
    "select_warehouse": {
        "uz": "Omborni tanlang:",
        "ru": "Выберите склад:",
        "en": "Select a warehouse:",
    },
    "select_source_warehouse": {
        "uz": "Qaysi ombordan ko'chirilayotganini tanlang:",
        "ru": "Выберите склад-источник:",
        "en": "Select source warehouse:",
    },
    "select_destination_warehouse": {
        "uz": "Qaysi omborga ko'chirilayotganini tanlang:",
        "ru": "Выберите склад-получатель:",
        "en": "Select destination warehouse:",
    },
    "no_active_warehouses": {
        "uz": "Hozircha faol omborlar mavjud emas.",
        "ru": "Сейчас нет активных складов.",
        "en": "There are no active warehouses right now.",
    },
    "same_branch_error": {
        "uz": "Manba va qabul qiluvchi filial bir xil bo'lishi mumkin emas.",
        "ru": "Филиал-источник и филиал-получатель не могут совпадать.",
        "en": "Source and destination branches must be different.",
    },
    "same_warehouse_error": {
        "uz": "Manba va qabul qiluvchi ombor bir xil bo'lishi mumkin emas.",
        "ru": "Склад-источник и склад-получатель не могут совпадать.",
        "en": "Source and destination warehouses must be different.",
    },
    "product_name_prompt": {
        "uz": "Mahsulot nomini kiriting:",
        "ru": "Введите название товара:",
        "en": "Enter product name:",
    },
    "quantity_prompt": {
        "uz": "Miqdorini kiriting:",
        "ru": "Введите количество:",
        "en": "Enter quantity:",
    },
    "unit_price_prompt": {
        "uz": "Narxini kiriting (1 kg yoki 1 dona uchun). Namuna: 140 000",
        "ru": "Введите цену (за 1 кг или 1 штуку). Пример: 140 000",
        "en": "Enter the price (per 1 kg or 1 piece). Example: 140 000",
    },
    "quantity_numeric_invalid": {
        "uz": "Faqat son kiriting. Namuna: 7, 7.5 yoki 1 000",
        "ru": "Введите только число. Пример: 7, 7.5 или 1 000",
        "en": "Enter numbers only. Example: 7, 7.5, or 1 000",
    },
    "unit_price_numeric_invalid": {
        "uz": "Narx uchun faqat son kiriting. Namuna: 8 000 yoki 140 000.5",
        "ru": "Введите для цены только число. Пример: 8 000 или 140 000.5",
        "en": "Enter numbers only for price. Example: 8 000 or 140 000.5",
    },
    "arrival_items_prompt": {
        "uz": "Kiritilgan mahsulotlar:\n{items}\n\nYana mahsulot qo'shasizmi yoki davom etasizmi?",
        "ru": "Добавленные товары:\n{items}\n\nДобавить еще товар или продолжить?",
        "en": "Added products:\n{items}\n\nDo you want to add another product or continue?",
    },
    "transfer_items_prompt": {
        "uz": "Kiritilgan mahsulotlar:\n{items}\n\nYana mahsulot qo'shasizmi yoki davom etasizmi?",
        "ru": "Добавленные товары:\n{items}\n\nДобавить еще товар или продолжить?",
        "en": "Added products:\n{items}\n\nDo you want to add another product or continue?",
    },
    "arrival_add_more": {
        "uz": "Yana qo'shish",
        "ru": "Добавить еще",
        "en": "Add another",
    },
    "arrival_continue": {
        "uz": "Davom etish",
        "ru": "Продолжить",
        "en": "Continue",
    },
    "arrival_photo_prompt": {
        "uz": "Nakladnoy rasmlarini yuboring. Kamida 1 ta rasm majburiy. Yuklab bo'lgach tugmani bosing.",
        "ru": "Отправьте фото накладной. Минимум 1 фото обязательно. После загрузки нажмите завершить.",
        "en": "Upload invoice photos. At least 1 photo is required. Press finish after uploading.",
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
        "uz": "Qo'shimcha ma'lumot yoki invoice tafsilotlarini matn ko'rinishida yozing.",
        "ru": "Введите дополнительную информацию или детали накладной вручную.",
        "en": "Enter additional information or invoice details manually.",
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
    "arrival_comment_prompt": {
        "uz": "Izoh yozing yoki o'tkazib yuboring.",
        "ru": "Введите комментарий или пропустите шаг.",
        "en": "Enter comment or skip this step.",
    },
    "skip_optional": {
        "uz": "O'tkazib yuborish",
        "ru": "Пропустить",
        "en": "Skip",
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
        "uz": "Rasm yuboring. Kamida 1 ta rasm majburiy. Yuklab bo'lgach tugmani bosing.",
        "ru": "Отправьте фото. Минимум 1 фото обязательно. После загрузки нажмите завершить.",
        "en": "Upload photos. At least 1 photo is required. Press finish after uploading.",
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
        "uz": "Avval kamida 1 ta rasm yuboring, keyin tugatish tugmasini bosing.",
        "ru": "Сначала загрузите хотя бы 1 фото, затем нажмите завершить.",
        "en": "Upload at least 1 photo first, then press finish.",
    },
    "photo_required_error": {
        "uz": "Bu operatsiya uchun rasm majburiy. Kamida 1 ta rasm yuboring.",
        "ru": "Для этой операции фото обязательно. Загрузите хотя бы 1 фото.",
        "en": "A photo is required for this operation. Upload at least 1 photo.",
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
    "back": {
        "uz": "⬅️ Orqaga",
        "ru": "⬅️ Назад",
        "en": "⬅️ Back",
    },
    "use_buttons": {
        "uz": "Iltimos, tugmalardan foydalaning.",
        "ru": "Пожалуйста, используйте кнопки.",
        "en": "Please use the buttons.",
    },
    "setgroup_usage": {
        "uz": "Guruhda /setgroup bar, /setgroup kitchen, /setgroup supplies yoki /setgroup meat ko'rinishida yuboring.",
        "ru": "В группе отправьте /setgroup bar, /setgroup kitchen, /setgroup supplies или /setgroup meat.",
        "en": "In the group send /setgroup bar, /setgroup kitchen, /setgroup supplies or /setgroup meat.",
    },
    "setgroup_group_only": {
        "uz": "Bu buyruq faqat guruh ichida ishlaydi.",
        "ru": "Эта команда работает только внутри группы.",
        "en": "This command works only inside a group.",
    },
    "setgroup_admin_only": {
        "uz": "Bu buyruqni faqat guruh admini ishlata oladi.",
        "ru": "Эту команду может использовать только администратор группы.",
        "en": "Only a group admin can use this command.",
    },
    "setgroup_unknown_warehouse": {
        "uz": "Noto'g'ri sklad. Ruxsat etilgan qiymatlar: bar, kitchen, supplies, meat.",
        "ru": "Неверный склад. Допустимые значения: bar, kitchen, supplies, meat.",
        "en": "Unknown warehouse. Allowed values: bar, kitchen, supplies, meat.",
    },
    "setgroup_success": {
        "uz": "\"{warehouse}\" skladi ushbu guruhga biriktirildi.",
        "ru": "Склад \"{warehouse}\" привязан к этой группе.",
        "en": "Warehouse \"{warehouse}\" has been linked to this group.",
    },
}


def t(key: str, lang: str, **kwargs: Any) -> str:
    selected = lang if lang in SUPPORTED_LANGUAGES else "uz"
    text = TRANSLATIONS.get(key, {}).get(selected) or TRANSLATIONS.get(key, {}).get("uz") or key
    if kwargs:
        return text.format(**kwargs)
    return text
