from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb(role: str = "customer"):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 Katalog", callback_data="catalog")
    builder.button(text="📦 Mening buyurtmalarim", callback_data="my_orders")
    if role in ("admin", "mahsulotchi"):
        builder.button(text="➕ Mahsulot qo'shish", callback_data="add_product")
    if role in ("admin", "courier"):
        builder.button(text="🚚 Kuryer paneli", callback_data="courier_panel")
    if role == "admin":
        builder.button(text="⚙️ Admin", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()


def categories_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Mavjud", callback_data="cat_mavjud")
    builder.button(text="🚚 Yo'lda", callback_data="cat_yolda")
    builder.button(text="📝 Buyurtma asosida", callback_data="cat_buyurtma")
    builder.button(text="⬅️ Orqaga", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def product_kb(product_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Sotib olish", callback_data=f"buy_{product_id}")
    builder.button(text="⬅️ Orqaga", callback_data="catalog")
    builder.adjust(1)
    return builder.as_markup()


def category_select_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Mavjud", callback_data="setcat_mavjud")
    builder.button(text="🚚 Yo'lda", callback_data="setcat_yolda")
    builder.button(text="📝 Buyurtma asosida", callback_data="setcat_buyurtma")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_add")
    builder.adjust(1)
    return builder.as_markup()


def confirm_order_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data="confirm_order")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(2)
    return builder.as_markup()


def location_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def remove_kb():
    return ReplyKeyboardRemove()


def courier_order_kb(order_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qabul qilish", callback_data=f"accept_{order_id}")
    builder.button(text="📍 Xarita", callback_data=f"map_{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def courier_active_kb(order_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🚚 Yetkazib berishni boshlash", callback_data=f"delivering_{order_id}")
    builder.button(text="✅ Yetkazib berildi", callback_data=f"delivered_{order_id}")
    builder.button(text="📍 Xarita", callback_data=f"map_{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def back_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Bosh menyu", callback_data="back_main")
    return builder.as_markup()
