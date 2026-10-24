from aiogram.fsm.state import State, StatesGroup


class AddProduct(StatesGroup):
    name = State()
    description = State()
    photo = State()
    price = State()
    category = State()


class OrderProduct(StatesGroup):
    quantity = State()
    confirm_location = State()
    waiting_location = State()


class EditProduct(StatesGroup):
    waiting_value = State()
