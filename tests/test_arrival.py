from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from app.bot.handlers.arrival import _submit_arrival, arrival_unit_price
from app.bot.states import ArrivalStates
from app.services.report_sender import ReportSender


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


def make_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=101,
        full_name="Bekhruz Mirzabaev",
        first_name="Bekhruz",
        last_name="Mirzabaev",
        username="bekhruz",
    )


class ArrivalFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_arrival_unit_price_collects_line_item_and_prompts_next_step(self) -> None:
        user = make_user()
        message = FakeMessage(text="140 000", from_user=user)
        state = FakeState(
            {
                "current_product_name": "ширбоз",
                "current_quantity": "15,2",
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
                    "quantity": "15,2",
                    "unit_price": "140 000",
                }
            ],
        )
        self.assertEqual(len(message.answers), 1)
        self.assertIn("ширбоз: 15,2*140 000", message.answers[0]["text"])
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
                        "quantity": "15,2",
                        "unit_price": "140 000",
                    },
                    {
                        "product_name": "рулет",
                        "quantity": "3",
                        "unit_price": "95 000",
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
        self.assertEqual(request_payload["quantity"], "15,2")
        self.assertEqual(len(request_payload["line_items"]), 2)
        self.assertTrue(state.cleared)
        self.assertIn("ID: 77", reply.answers[0]["text"])

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
                        "quantity": "15,2",
                        "unit_price": "140 000",
                    },
                    {
                        "product_name": "рулет",
                        "quantity": "3",
                        "unit_price": "95 000",
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
        self.assertIn("⚠️ <b>Номенклатура:</b>\n• ширбоз — 15,2 × 140 000\n• рулет — 3 × 95 000", caption)
        self.assertIn("🚚 <b>Поставщик:</b> бобо", caption)
        self.assertIn("📷 <b>Фото:</b> нет", caption)
        self.assertLess(
            caption.index("🚚 <b>Поставщик:</b> бобо"),
            caption.index("⚠️ <b>Номенклатура:</b>"),
        )

    def test_report_sender_caption_lists_transfer_header(self) -> None:
        sender = ReportSender(bot=SimpleNamespace(), settings=SimpleNamespace(), db=SimpleNamespace())
        caption = sender._build_caption(
            {
                "operation_type": "transfer",
                "transfer_type": "warehouse",
                "branch": "Geofizika",
                "warehouse": "Бар",
                "source_warehouse": "Кухня",
                "date": date(2026, 3, 18),
                "product_name": "Kola",
                "quantity": "10",
            },
            {
                "name": "Sharif Abdurakhmonov",
                "phone_number": "998931434413",
            },
            photos_count=2,
        )

        self.assertIn("🔄 <b>Peremesheniya</b>", caption)
        self.assertIn("📤 <b>Со склада:</b> Кухня", caption)
        self.assertIn("📥 <b>На склад:</b> Бар", caption)
        self.assertIn("📷 <b>Фото:</b> 2 шт.", caption)


if __name__ == "__main__":
    unittest.main()
