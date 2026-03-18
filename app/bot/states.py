from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_phone = State()


class ArrivalStates(StatesGroup):
    selecting_branch = State()
    selecting_warehouse = State()
    waiting_product_name = State()
    waiting_quantity = State()
    waiting_unit_price = State()
    confirming_items = State()
    collecting_photos = State()
    manual_input = State()
    waiting_supplier = State()
    waiting_date = State()
    waiting_comment = State()


class TransferStates(StatesGroup):
    selecting_transfer_kind = State()
    selecting_source_branch = State()
    selecting_branch = State()
    selecting_source_warehouse = State()
    selecting_warehouse = State()
    waiting_product_name = State()
    waiting_quantity = State()
    waiting_comment = State()
    collecting_optional_photos = State()
