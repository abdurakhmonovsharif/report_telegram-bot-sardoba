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


class ActRazboraStates(StatesGroup):
    selecting_branch = State()
    waiting_product_name = State()
    waiting_total_quantity = State()
    waiting_nomenclature_name = State()
    waiting_nomenclature_quantity = State()
    confirming_items = State()
    waiting_date = State()
