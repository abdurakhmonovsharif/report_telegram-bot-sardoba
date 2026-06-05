from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from app.bot.handlers.arrival import (
    _submit_arrival,
    arrival_photos_done,
    arrival_product_name,
    arrival_quantity,
    arrival_unit_price,
)
from app.bot.handlers.act_razbora import (
    act_razbora_date,
    act_razbora_finalize,
    act_razbora_nomenclature_quantity,
    act_razbora_product_name,
    act_razbora_total_quantity,
)
from app.bot.handlers.start import _normalize_operation_group_target
from app.bot.i18n import t
from app.bot.keyboards import act_razbora_items_keyboard
from app.bot.states import ActRazboraStates, ArrivalStates
from app.core.numeric import format_numeric_value, is_valid_numeric_value
from app.services.report_sender import ReportSender
from app.services.request_service import ReportDeliveryError


class FakeState:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
        self.current_state = None
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state

    async def clear(self) -> None:
        self.data = {}
        self.current_state = None
        self.cleared = True


class FakeMessage:
    def __init__(self, text: str = "", from_user=None) -> None:
        self.text = text
        self.from_user = from_user
        self.answers: list[dict] = []
        self.deleted = False

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})

    async def delete(self) -> None:
        self.deleted = True


class FakeCallback:
    def __init__(self, *, data: str, from_user=None, message: FakeMessage | None = None) -> None:
        self.data = data
        self.from_user = from_user
        self.message = message
        self.answers: list[dict] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append({"text": text, "show_alert": show_alert})


class FakeDB:
    def __init__(self, *, language: str = "uz") -> None:
        self.language = language

    async def upsert_user(self, telegram_id: int, name: str, **kwargs) -> dict:
        return {
            "id": 1,
            "telegram_id": telegram_id,
            "name": name,
            "language": self.language,
        }


class FakeRequestService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def finalize_request(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"id": 77}


class FailingRequestService:
    async def finalize_request(self, **kwargs) -> dict:
        raise ReportDeliveryError(91)


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, *, chat_id: int, text: str) -> None:
        self.messages.append({"chat_id": chat_id, "text": text})


class FakeReportDB:
    def __init__(self, binding: dict | None = None) -> None:
        self.binding = binding

    async def get_operation_group_binding(self, operation_type: str) -> dict | None:
        return self.binding if operation_type == "act_razbora" else None


def make_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=101,
        full_name="Bekhruz Mirzabaev",
        first_name="Bekhruz",
        last_name="Mirzabaev",
        username="bekhruz",
    )


class NumericFormattingTests(unittest.TestCase):
    def test_numeric_formatting_allows_single_grouping_space(self) -> None:
        self.assertTrue(is_valid_numeric_value("140 000"))
        self.assertFalse(is_valid_numeric_value("140  000"))
        self.assertEqual(format_numeric_value("140000"), "140 000")
        self.assertEqual(format_numeric_value("140 000"), "140 000")

    def test_setgroup_normalizes_act_razbora_alias(self) -> None:
        self.assertEqual(_normalize_operation_group_target("aktrazbora"), "act_razbora")
        self.assertEqual(_normalize_operation_group_target("act-razbora"), "act_razbora")
        self.assertIsNone(_normalize_operation_group_target("bar"))

    def test_act_razbora_empty_items_keyboard_prompts_add_and_finish(self) -> None:
        markup = act_razbora_items_keyboard("uz", has_items=False)

        self.assertEqual(markup.inline_keyboard[0][0].text, "Nomenklatura qo‘shish")
        self.assertEqual(markup.inline_keyboard[0][1].text, "Yakunlash")

    def test_act_razbora_existing_items_keyboard_prompts_add_more_and_finish(self) -> None:
        markup = act_razbora_items_keyboard("uz", has_items=True)

        self.assertEqual(markup.inline_keyboard[0][0].text, "Yana qo‘shish")
        self.assertEqual(markup.inline_keyboard[0][1].text, "Yakunlash")


class ArrivalFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_arrival_product_flow_is_sequential(self) -> None:
        user = make_user()
        state = FakeState({})

        product_message = FakeMessage(text="ширбоз", from_user=user)
        await arrival_product_name(product_message, state, FakeDB())

        self.assertIs(state.current_state, ArrivalStates.waiting_quantity)
        self.assertEqual(state.data["current_product_name"], "ширбоз")
        self.assertEqual(product_message.answers[0]["text"], t("quantity_prompt", "uz"))

        quantity_message = FakeMessage(text="15.2", from_user=user)
        await arrival_quantity(quantity_message, state, FakeDB())

        self.assertIs(state.current_state, ArrivalStates.waiting_unit_price)
        self.assertEqual(state.data["current_quantity"], "15.2")
        self.assertEqual(quantity_message.answers[0]["text"], t("unit_price_prompt", "uz"))

    async def test_arrival_unit_price_collects_line_item_and_prompts_next_step(self) -> None:
        user = make_user()
        message = FakeMessage(text="140 000", from_user=user)
        state = FakeState(
            {
                "current_product_name": "ширбоз",
                "current_quantity": "15.2",
                "line_items": [],
            }
        )

        await arrival_unit_price(message, state, FakeDB())

        self.assertIs(state.current_state, ArrivalStates.confirming_items)
        self.assertEqual(
            state.data["line_items"],
            [
                {
                    "product_name": "ширбоз",
                    "quantity": "15.2",
                    "unit_price": "140 000",
                }
            ],
        )
        self.assertEqual(len(message.answers), 1)
        self.assertIn("ширбоз: 15.2*140 000", message.answers[0]["text"])
        self.assertIsNotNone(message.answers[0]["reply_markup"])

    async def test_submit_arrival_success_sends_line_items_to_request_service(self) -> None:
        user = make_user()
        reply = FakeMessage(from_user=user)
        state = FakeState(
            {
                "branch": "Mk5",
                "warehouse": "Мясо",
                "branch_id": 4,
                "warehouse_id": 4,
                "supplier_name": "бобо",
                "request_date": date(2026, 3, 18),
                "comment": None,
                "info_text": None,
                "line_items": [
                    {
                        "product_name": "ширбоз",
                        "quantity": "15.2",
                        "unit_price": "140000",
                    },
                    {
                        "product_name": "рулет",
                        "quantity": "3",
                        "unit_price": "95000",
                    },
                ],
                "photos": [],
            }
        )
        request_service = FakeRequestService()

        await _submit_arrival(
            state=state,
            db=FakeDB(),
            request_service=request_service,
            from_user=user,
            reply=reply,
        )

        self.assertEqual(len(request_service.calls), 1)
        request_payload = request_service.calls[0]
        self.assertEqual(request_payload["product_name"], "ширбоз")
        self.assertEqual(request_payload["quantity"], "15.2")
        self.assertEqual(len(request_payload["line_items"]), 2)
        self.assertEqual(request_payload["line_items"][0]["unit_price"], "140 000")
        self.assertEqual(request_payload["line_items"][1]["unit_price"], "95 000")
        self.assertTrue(state.cleared)
        self.assertIn("ID: 77", reply.answers[0]["text"])

    async def test_arrival_photos_done_requires_uploaded_photo(self) -> None:
        user = make_user()
        callback_message = FakeMessage(from_user=user)
        callback = FakeCallback(data="arrival:photos_done", from_user=user, message=callback_message)
        state = FakeState({"photos": []})

        await arrival_photos_done(callback, state, FakeDB())

        self.assertEqual(len(callback_message.answers), 1)
        self.assertEqual(callback_message.answers[0]["text"], t("upload_photo_or_finish", "uz"))
        self.assertEqual(len(callback.answers), 1)

    async def test_submit_arrival_failure_still_returns_request_id(self) -> None:
        user = make_user()
        reply = FakeMessage(from_user=user)
        state = FakeState(
            {
                "branch": "Mk5",
                "warehouse": "Мясо",
                "line_items": [{"product_name": "ширбоз", "quantity": "15.2", "unit_price": "140000"}],
                "photos": [],
            }
        )

        await _submit_arrival(
            state=state,
            db=FakeDB(),
            request_service=FailingRequestService(),
            from_user=user,
            reply=reply,
        )

        self.assertTrue(state.cleared)
        self.assertIn("ID: 91", reply.answers[0]["text"])

    def test_report_sender_caption_lists_all_arrival_items_and_document_date(self) -> None:
        sender = ReportSender(bot=SimpleNamespace(), settings=SimpleNamespace(), db=SimpleNamespace())
        caption = sender._build_caption(
            {
                "operation_type": "arrival",
                "branch": "Mk5",
                "warehouse": "Мясо",
                "date": date(2026, 3, 18),
                "line_items": [
                    {
                        "product_name": "ширбоз",
                        "quantity": "15.2",
                        "unit_price": "140000",
                    },
                    {
                        "product_name": "рулет",
                        "quantity": "3",
                        "unit_price": "95000",
                    },
                ],
                "supplier_name": "бобо",
            },
            {
                "name": "Bekhruz Mirzabaev",
                "phone_number": "+998990240505",
            },
            photos_count=0,
        )

        self.assertIn("📦 <b>Prixod</b>", caption)
        self.assertIn("📆 <b>Дата:</b> 18/03/2026", caption)
        self.assertIn("⚠️ <b>Номенклатура:</b>\n• ширбоз — 15.2 × 140 000\n• рулет — 3 × 95 000", caption)
        self.assertIn("🚚 <b>Поставщик:</b> бобо", caption)
        self.assertIn("📷 <b>Фото:</b> нет", caption)
        self.assertLess(
            caption.index("🚚 <b>Поставщик:</b> бобо"),
            caption.index("⚠️ <b>Номенклатура:</b>"),
        )

    def test_report_sender_caption_lists_act_razbora_header(self) -> None:
        sender = ReportSender(bot=SimpleNamespace(), settings=SimpleNamespace(), db=SimpleNamespace())
        caption = sender._build_caption(
            {
                "operation_type": "act_razbora",
                "branch": "Geofizika",
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "date": date(2026, 3, 18),
                "line_items": [
                    {
                        "product_name": "Qiyma uchun",
                        "quantity": "20",
                    },
                    {
                        "product_name": "Kabob uchun",
                        "quantity": "15",
                    },
                ],
            },
            {
                "name": "Sharif Abdurakhmonov",
                "phone_number": "998931434413",
            },
            photos_count=2,
        )

        self.assertIn("🧾 <b>Акт разбора</b>", caption)
        self.assertIn("📍 <b>Филиал:</b> Geofizika", caption)
        self.assertIn("🥩 <b>Маҳсулот:</b> Qo&#x27;y go&#x27;shti", caption)
        self.assertIn("⚖️ <b>Жами кг:</b> 100 kg", caption)
        self.assertIn("⚠️ <b>Номенклатура:</b>\n• Qiyma uchun — 20 kg\n• Kabob uchun — 15 kg", caption)
        self.assertNotIn("📷 <b>Фото:</b>", caption)

    async def test_report_sender_sends_act_razbora_to_default_group(self) -> None:
        bot = FakeBot()
        sender = ReportSender(
            bot=bot,
            settings=SimpleNamespace(default_report_chat_id=-100123),
            db=FakeReportDB(),
        )

        await sender.send_request_report(
            request_record={
                "id": 10,
                "operation_type": "act_razbora",
                "branch": "Geofizika",
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "line_items": [],
            },
            photos=[],
            user_record={"name": "Ali Valiyev", "phone_number": "+998901234567"},
        )

        self.assertEqual(bot.messages[0]["chat_id"], -100123)
        self.assertIn("🧾 <b>Акт разбора</b>", bot.messages[0]["text"])

    async def test_report_sender_prefers_bound_act_razbora_group(self) -> None:
        bot = FakeBot()
        sender = ReportSender(
            bot=bot,
            settings=SimpleNamespace(default_report_chat_id=-100123),
            db=FakeReportDB(binding={"group_chat_id": -100999}),
        )

        await sender.send_request_report(
            request_record={
                "id": 11,
                "operation_type": "act_razbora",
                "branch": "Geofizika",
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "line_items": [],
            },
            photos=[],
            user_record={"name": "Ali Valiyev", "phone_number": "+998901234567"},
        )

        self.assertEqual(bot.messages[0]["chat_id"], -100999)


class ActRazboraFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_act_razbora_product_flow_is_sequential(self) -> None:
        user = make_user()
        state = FakeState({})

        product_message = FakeMessage(text="Qo'y go'shti", from_user=user)
        await act_razbora_product_name(product_message, state, FakeDB())

        self.assertIs(state.current_state, ActRazboraStates.waiting_total_quantity)
        self.assertEqual(state.data["product_name"], "Qo'y go'shti")
        self.assertEqual(product_message.answers[0]["text"], t("act_razbora_total_quantity_prompt", "uz"))

        quantity_message = FakeMessage(text="100", from_user=user)
        await act_razbora_total_quantity(quantity_message, state, FakeDB())

        self.assertIs(state.current_state, ActRazboraStates.confirming_items)
        self.assertEqual(state.data["quantity"], "100")
        self.assertEqual(state.data["line_items"], [])

    async def test_act_razbora_finalize_asks_for_manual_date(self) -> None:
        user = make_user()
        callback_message = FakeMessage(from_user=user)
        callback = FakeCallback(data="act_razbora:items_done", from_user=user, message=callback_message)
        state = FakeState(
            {
                "branch": "Geofizika",
                "branch_id": 1,
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "line_items": [],
            }
        )
        request_service = FakeRequestService()

        await act_razbora_finalize(callback, state, FakeDB(), request_service)

        self.assertEqual(len(request_service.calls), 0)
        self.assertIs(state.current_state, ActRazboraStates.waiting_date)
        self.assertEqual(callback_message.answers[0]["text"], t("date_prompt", "uz"))

    async def test_act_razbora_date_submits_request_after_manual_date(self) -> None:
        user = make_user()
        message = FakeMessage(text="2026-03-18", from_user=user)
        state = FakeState(
            {
                "branch": "Geofizika",
                "branch_id": 1,
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "line_items": [],
            }
        )
        request_service = FakeRequestService()

        await act_razbora_date(message, state, FakeDB(), request_service)

        self.assertEqual(len(request_service.calls), 1)
        request_payload = request_service.calls[0]
        self.assertEqual(request_payload["operation_type"], "act_razbora")
        self.assertEqual(request_payload["product_name"], "Qo'y go'shti")
        self.assertEqual(request_payload["quantity"], "100")
        self.assertEqual(request_payload["request_date"], date(2026, 3, 18))
        self.assertEqual(request_payload["line_items"], [])
        self.assertEqual(request_payload["photos"], [])
        self.assertTrue(state.cleared)

    async def test_act_razbora_finalize_submits_manual_date_without_photo(self) -> None:
        user = make_user()
        callback_message = FakeMessage(from_user=user)
        callback = FakeCallback(data="act_razbora:items_done", from_user=user, message=callback_message)
        state = FakeState(
            {
                "branch": "Geofizika",
                "branch_id": 1,
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "request_date": date(2026, 3, 18),
                "line_items": [],
            }
        )
        request_service = FakeRequestService()

        await act_razbora_finalize(callback, state, FakeDB(), request_service)

        self.assertEqual(len(request_service.calls), 1)
        request_payload = request_service.calls[0]
        self.assertEqual(request_payload["operation_type"], "act_razbora")
        self.assertEqual(request_payload["product_name"], "Qo'y go'shti")
        self.assertEqual(request_payload["quantity"], "100")
        self.assertEqual(request_payload["request_date"], date(2026, 3, 18))
        self.assertEqual(request_payload["line_items"], [])
        self.assertEqual(request_payload["photos"], [])
        self.assertTrue(state.cleared)

    async def test_act_razbora_date_rejects_invalid_date(self) -> None:
        user = make_user()
        message = FakeMessage(text="18/03/2026", from_user=user)
        state = FakeState(
            {
                "branch": "Geofizika",
                "branch_id": 1,
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "line_items": [],
            }
        )
        request_service = FakeRequestService()

        await act_razbora_date(message, state, FakeDB(), request_service)

        self.assertEqual(len(request_service.calls), 0)
        self.assertEqual(message.answers[0]["text"], t("date_invalid", "uz"))
        self.assertFalse(state.cleared)

    async def test_act_razbora_nomenclature_quantity_must_not_exceed_total(self) -> None:
        user = make_user()
        message = FakeMessage(text="20", from_user=user)
        state = FakeState(
            {
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "current_nomenclature_name": "Kabob uchun",
                "line_items": [{"product_name": "Qiyma uchun", "quantity": "90"}],
            }
        )

        await act_razbora_nomenclature_quantity(message, state, FakeDB())

        self.assertIsNone(state.current_state)
        self.assertEqual(state.data["line_items"], [{"product_name": "Qiyma uchun", "quantity": "90"}])
        self.assertEqual(message.answers[0]["text"], t("act_razbora_quantity_exceeded", "uz", total="100"))

    async def test_act_razbora_nomenclature_quantity_returns_to_items_after_valid_item(self) -> None:
        user = make_user()
        message = FakeMessage(text="20", from_user=user)
        state = FakeState(
            {
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "current_nomenclature_name": "Qiyma uchun",
                "line_items": [],
            }
        )

        await act_razbora_nomenclature_quantity(message, state, FakeDB())

        self.assertIs(state.current_state, ActRazboraStates.confirming_items)
        self.assertEqual(state.data["line_items"], [{"product_name": "Qiyma uchun", "quantity": "20"}])
        markup = message.answers[0]["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].text, t("act_razbora_add_more", "uz"))
        self.assertEqual(markup.inline_keyboard[0][1].text, t("act_razbora_finish", "uz"))

    async def test_act_razbora_failure_still_returns_request_id(self) -> None:
        user = make_user()
        callback_message = FakeMessage(from_user=user)
        callback = FakeCallback(data="act_razbora:items_done", from_user=user, message=callback_message)
        state = FakeState(
            {
                "branch": "Geofizika",
                "branch_id": 1,
                "warehouse": "Без склада",
                "product_name": "Qo'y go'shti",
                "quantity": "100",
                "request_date": date(2026, 3, 18),
                "line_items": [{"product_name": "Qiyma uchun", "quantity": "20"}],
            }
        )

        await act_razbora_finalize(callback, state, FakeDB(), FailingRequestService())

        self.assertTrue(state.cleared)
        self.assertIn("ID: 91", callback_message.answers[0]["text"])


if __name__ == "__main__":
    unittest.main()
