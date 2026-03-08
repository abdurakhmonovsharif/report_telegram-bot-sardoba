from aiogram.fsm.state import State, StatesGroup


class ArrivalStates(StatesGroup):
    selecting_branch = State()
    selecting_warehouse = State()
    collecting_photos = State()
    manual_input = State()
    waiting_supplier = State()
    waiting_date = State()


class TransferStates(StatesGroup):
    selecting_branch = State()
    selecting_warehouse = State()
    waiting_comment = State()
    collecting_optional_photos = State()
