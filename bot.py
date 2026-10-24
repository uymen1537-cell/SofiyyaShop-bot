import asyncio
import math
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import (
    BOT_TOKEN, ADMIN_IDS, CHANNEL_ID, SHOP_LAT, SHOP_LON,
    DELIVERY_PRICE_PER_KM, MIN_DELIVERY_PRICE, MAX_DELIVERY_KM,
    EST_TIME_MAVJUD, EST_TIME_YOLDA, EST_TIME_BUYURTMA
)
from database import (
    init_db, get_or_create_user, add_product, set_channel_message_id,
    get_products_by_category, get_product, create_order, get_order,
    get_new_orders, accept_order, update_order_status, get_user_orders,
    get_courier_orders, get_all_products, deactivate_product, activate_product,
    update_product
)
from states import AddProduct, OrderProduct, EditProduct
from keyboards import (
    main_menu_kb, categories_kb, product_kb, category_select_kb,
    confirm_order_kb, location_kb, remove_kb, courier_order_kb,
    courier_active_kb, back_main_kb
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ========== YORDAMCHI FUNKSIYALAR ==========
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Yer radiusi km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def calc_delivery(lat, lon):
    dist = haversine(SHOP_LAT, SHOP_LON, lat, lon)
    if dist > MAX_DELIVERY_KM:
        return None, dist
    price = max(MIN_DELIVERY_PRICE, int(dist * DELIVERY_PRICE_PER_KM))
    return price, dist


def category_name(cat: str) -> str:
    return {
        "mavjud": "✅ Mavjud",
        "yolda": "🚚 Yo'lda",
        "buyurtma": "📝 Buyurtma asosida"
    }.get(cat, cat)


def est_time(cat: str) -> int:
    return {
        "mavjud": EST_TIME_MAVJUD,
        "yolda": EST_TIME_YOLDA,
        "buyurtma": EST_TIME_BUYURTMA
    }.get(cat, 120)


def format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ") + " so'm"


# ========== START ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )
    role = user.get("role", "customer")
    text = (
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        f"🛍 <b>SofiyyaShop</b> botiga xush kelibsiz.\n"
        f"Kategoriyalar: Mavjud · Yo'lda · Buyurtma asosida\n\n"
        f"Quyidagi menyudan tanlang:"
    )
    await message.answer(text, reply_markup=main_menu_kb(role))


@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(callback.from_user.id)
    await callback.message.edit_text(
        "Bosh menyu:",
        reply_markup=main_menu_kb(user.get("role", "customer"))
    )
    await callback.answer()


# ========== KATALOG ==========
@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.edit_text(
        "📂 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cat_"))
async def show_category_products(callback: CallbackQuery):
    cat = callback.data.replace("cat_", "")
    products = await get_products_by_category(cat)
    if not products:
        await callback.message.edit_text(
            f"{category_name(cat)} kategoriyasida hozircha mahsulot yo'q.",
            reply_markup=categories_kb()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"<b>{category_name(cat)}</b> — {len(products)} ta mahsulot:\n"
        f"Mahsulotni ko'rish uchun tanlang:",
        reply_markup=await products_list_kb(products)
    )
    await callback.answer()


async def products_list_kb(products):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for p in products[:30]:  # max 30
        builder.button(
            text=f"{p['name'][:30]} — {format_price(p['price'])}",
            callback_data=f"prod_{p['id']}"
        )
    builder.button(text="⬅️ Orqaga", callback_data="catalog")
    builder.adjust(1)
    return builder.as_markup()


@dp.callback_query(F.data.startswith("prod_"))
async def show_product(callback: CallbackQuery):
    product_id = int(callback.data.replace("prod_", ""))
    product = await get_product(product_id)
    if not product or not product["is_active"]:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    caption = (
        f"<b>{product['name']}</b>\n\n"
        f"{product['description'] or ''}\n\n"
        f"💰 Narxi: <b>{format_price(product['price'])}</b>\n"
        f"📂 {category_name(product['category'])}\n"
        f"⏱ Taxminiy yetkazish: ~{est_time(product['category'])} daqiqa"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await bot.send_photo(
        chat_id=callback.from_user.id,
        photo=product["photo_file_id"],
        caption=caption,
        reply_markup=product_kb(product_id)
    )
    await callback.answer()


# ========== MAHSULOT QO'SHISH (Admin / Mahsulotchi) ==========
@dp.callback_query(F.data == "add_product")
async def start_add_product(callback: CallbackQuery, state: FSMContext):
    user = await get_or_create_user(callback.from_user.id)
    if user.get("role") not in ("admin", "mahsulotchi"):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    await state.set_state(AddProduct.name)
    await callback.message.edit_text(
        "➕ <b>Yangi mahsulot qo'shish</b>\n\n"
        "1-qadam: Mahsulot <b>nomini</b> yozing:"
    )
    await callback.answer()


@dp.message(AddProduct.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProduct.description)
    await message.answer("2-qadam: <b>Tavsifini</b> yozing (yoki - deb o'tkazib yuboring):")


@dp.message(AddProduct.description)
async def process_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    if desc == "-":
        desc = ""
    await state.update_data(description=desc)
    await state.set_state(AddProduct.photo)
    await message.answer("3-qadam: Mahsulot <b>rasmini</b> yuboring:")


@dp.message(AddProduct.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_id)
    await state.set_state(AddProduct.price)
    await message.answer("4-qadam: <b>Narxini</b> yozing (faqat raqam, so'mda):")


@dp.message(AddProduct.photo)
async def process_photo_invalid(message: Message):
    await message.answer("Iltimos, rasm yuboring.")


@dp.message(AddProduct.price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Noto'g'ri narx. Faqat musbat raqam yozing:")
        return
    await state.update_data(price=price)
    await state.set_state(AddProduct.category)
    await message.answer(
        "5-qadam: <b>Kategoriyani</b> tanlang:",
        reply_markup=category_select_kb()
    )


@dp.callback_query(F.data.startswith("setcat_"), AddProduct.category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.replace("setcat_", "")
    data = await state.get_data()
    await state.clear()

    product_id = await add_product(
        name=data["name"],
        description=data.get("description", ""),
        photo_file_id=data["photo_file_id"],
        price=data["price"],
        category=cat,
        added_by=callback.from_user.id
    )

    # Kanalga joylash
    caption = (
        f"<b>{data['name']}</b>\n\n"
        f"{data.get('description', '')}\n\n"
        f"💰 <b>{format_price(data['price'])}</b>\n"
        f"📂 {category_name(cat)}\n\n"
        f"🛒 Sotib olish uchun botga o'ting"
    )
    try:
        if CHANNEL_ID:
            msg = await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=data["photo_file_id"],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="🛒 Sotib olish",
                        url=f"https://t.me/{(await bot.me()).username}?start=prod_{product_id}"
                    )
                ]])
            )
            await set_channel_message_id(product_id, msg.message_id)
    except Exception as e:
        logger.error(f"Kanalga yuborishda xato: {e}")

    await callback.message.edit_text(
        f"✅ Mahsulot qo'shildi!\n\n"
        f"<b>{data['name']}</b>\n"
        f"{format_price(data['price'])} · {category_name(cat)}\n"
        f"ID: {product_id}",
        reply_markup=back_main_kb()
    )
    await callback.answer("Saqlandi!")


@dp.callback_query(F.data == "cancel_add")
async def cancel_add(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.", reply_markup=back_main_kb())
    await callback.answer()


# ========== SOTIB OLISH ==========
@dp.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.replace("buy_", ""))
    product = await get_product(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    await state.update_data(product_id=product_id, product=product)
    await state.set_state(OrderProduct.quantity)
    await callback.message.answer(
        f"<b>{product['name']}</b>\n"
        f"Narxi: {format_price(product['price'])}\n\n"
        f"Nechta dona olasiz? (raqam yozing):"
    )
    await callback.answer()


@dp.message(OrderProduct.quantity)
async def process_quantity(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
        if qty <= 0 or qty > 50:
            raise ValueError
    except ValueError:
        await message.answer("1 dan 50 gacha raqam yozing:")
        return

    data = await state.get_data()
    product = data["product"]
    total_product = product["price"] * qty

    await state.update_data(quantity=qty, product_total=total_product)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🚚 Yetkazib berish", callback_data="delivery_yes")
    builder.button(text="📍 Tarqatish punktidan olib ketaman", callback_data="pickup_point")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(1)

    await message.answer(
        f"📦 {qty} dona · {format_price(total_product)}\n\n"
        f"Qanday qilib olasiz?",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "delivery_yes")
async def choose_delivery(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderProduct.waiting_location)
    await callback.message.answer(
        "Yetkazib berish uchun <b>lokatsiyangizni</b> yuboring.\n"
        "(Xaritadan aniq joyingizni tanlang)",
        reply_markup=location_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "pickup_point")
async def choose_pickup(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product = data["product"]
    qty = data["quantity"]
    product_total = data["product_total"]
    minutes = est_time(product["category"])

    # Yetkazib berish 0 so'm
    await state.update_data(
        lat=SHOP_LAT, lon=SHOP_LON, delivery_price=0, total=product_total,
        dist=0, estimated_minutes=minutes, is_pickup=True
    )
    await state.set_state(OrderProduct.confirm_location)

    await callback.message.answer(
        f"📍 <b>Tarqatish punkti lokatsiyasi:</b>"
    )
    await bot.send_location(callback.from_user.id, SHOP_LAT, SHOP_LON)

    await callback.message.answer(
        f"📦 {qty} dona · {format_price(product_total)}\n"
        f"🚚 Yetkazib berish: <b>0 so'm</b> (o'zingiz olasiz)\n"
        f"━━━━━━━━━━━━\n"
        f"💵 <b>Jami: {format_price(product_total)}</b>\n"
        f"⏱ Taxminiy tayyor bo'lish: ~{minutes} daqiqa\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=confirm_order_kb()
    )
    await callback.answer()


@dp.message(OrderProduct.waiting_location, F.location)
async def process_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    price, dist = calc_delivery(lat, lon)

    if price is None:
        await message.answer(
            f"⚠️ <b>Uzoq manzil!</b>\n\n"
            f"Sizning joyingiz olib ketish punktidan <b>{dist:.1f} km</b> uzoqda.\n"
            f"Biz faqat <b>{int(MAX_DELIVERY_KM)} km</b> gacha yetkazib beramiz.\n\n"
            f"Iltimos, yaqinroq manzil yuboring yoki tarqatish punktidan olib keting.",
            reply_markup=remove_kb()
        )
        return

    data = await state.get_data()
    product = data["product"]
    qty = data["quantity"]
    product_total = data["product_total"]
    total = product_total + price
    minutes = est_time(product["category"])

    await state.update_data(
        lat=lat, lon=lon, delivery_price=price, total=total,
        dist=dist, estimated_minutes=minutes
    )
    await state.set_state(OrderProduct.confirm_location)

    await message.answer(
        f"📍 Masofa: <b>{dist:.1f} km</b>\n"
        f"🚚 Yetkazib berish: <b>{format_price(price)}</b>\n"
        f"📦 Mahsulot ({qty} dona): {format_price(product_total)}\n"
        f"━━━━━━━━━━━━\n"
        f"💵 <b>Jami: {format_price(total)}</b>\n"
        f"⏱ Taxminiy vaqt: ~{minutes} daqiqa\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=confirm_order_kb()
    )
    await message.answer(".", reply_markup=remove_kb())  # klaviaturani yashirish


@dp.message(OrderProduct.waiting_location)
async def process_location_invalid(message: Message):
    await message.answer("Iltimos, lokatsiya yuboring (📍 tugma orqali).")


@dp.callback_query(F.data == "confirm_order", OrderProduct.confirm_location)
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await get_or_create_user(callback.from_user.id)

    order_id = await create_order(
        user_id=user["id"],
        product_id=data["product_id"],
        quantity=data["quantity"],
        product_price=data["product"]["price"],
        delivery_price=data["delivery_price"],
        total=data["total"],
        lat=data["lat"],
        lon=data["lon"],
        address_text=f"{data['lat']:.5f}, {data['lon']:.5f}",
        estimated_minutes=data["estimated_minutes"]
    )
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
        f"Buyurtma №{order_id}\n"
        f"Jami: {format_price(data['total'])}\n"
        f"Taxminiy yetkazish: ~{data['estimated_minutes']} daqiqa\n\n"
        f"Kuryer tez orada bog'lanadi.",
        reply_markup=back_main_kb()
    )
    await callback.answer()

    # Kuryerlarga xabar (faqat kuryerlarga)
    order = await get_order(order_id)
    text = (
        f"🆕 <b>Yangi buyurtma №{order_id}</b>\n\n"
        f"📦 {order['product_name']} × {order['quantity']}\n"
        f"👤 {order['user_name']} (@{order['user_username'] or '—'})\n"
        f"💰 {format_price(order['total_price'])}\n"
        f"📍 {order['lat']:.5f}, {order['lon']:.5f}\n"
        f"Masofa: {data['dist']:.1f} km"
    )
    from config import COURIER_IDS
    # Faqat kuryerlarga (qabul qilish tugmasi bilan)
    for cid in set(COURIER_IDS):
        try:
            await bot.send_message(cid, text, reply_markup=courier_order_kb(order_id))
            await bot.send_location(cid, order["lat"], order["lon"])
        except Exception as e:
            logger.warning(f"Kuryerga yuborib bo'lmadi {cid}: {e}")
    # Adminlarga oddiy xabar (tugmasiz)
    for aid in set(ADMIN_IDS):
        if aid not in COURIER_IDS:
            try:
                await bot.send_message(aid, f"ℹ️ Yangi buyurtma №{order_id} yaratildi.\n{order['product_name']} — {format_price(order['total_price'])}")
            except Exception:
                pass


@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Buyurtma bekor qilindi.", reply_markup=back_main_kb())
    await callback.answer()


# ========== KURYER PANELI ==========
@dp.callback_query(F.data == "courier_panel")
async def courier_panel(callback: CallbackQuery):
    user = await get_or_create_user(callback.from_user.id)
    if user.get("role") not in ("admin", "courier"):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    new_orders = await get_new_orders()
    my_orders = await get_courier_orders(callback.from_user.id)

    text = "🚚 <b>Kuryer paneli</b>\n\n"
    if new_orders:
        text += f"🆕 Yangi buyurtmalar: {len(new_orders)} ta\n"
    else:
        text += "Yangi buyurtma yo'q.\n"
    if my_orders:
        text += f"📋 Mening faol buyurtmalarim: {len(my_orders)} ta\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for o in new_orders[:10]:
        builder.button(
            text=f"🆕 №{o['id']} — {o['product_name'][:20]}",
            callback_data=f"vieworder_{o['id']}"
        )
    for o in my_orders[:10]:
        builder.button(
            text=f"📋 №{o['id']} — {o['status']}",
            callback_data=f"vieworder_{o['id']}"
        )
    builder.button(text="⬅️ Orqaga", callback_data="back_main")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data.startswith("vieworder_"))
async def view_order(callback: CallbackQuery):
    order_id = int(callback.data.replace("vieworder_", ""))
    order = await get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    text = (
        f"<b>Buyurtma №{order['id']}</b>\n"
        f"Status: {order['status']}\n\n"
        f"📦 {order['product_name']} × {order['quantity']}\n"
        f"👤 {order['user_name']} (@{order['user_username'] or '—'})\n"
        f"💰 Jami: {format_price(order['total_price'])}\n"
        f"🚚 Yetkazish: {format_price(order['delivery_price'])}\n"
        f"📍 {order['lat']:.5f}, {order['lon']:.5f}"
    )

    if order["status"] == "new":
        kb = courier_order_kb(order_id)
    else:
        kb = courier_active_kb(order_id)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("accept_"))
async def accept_order_cb(callback: CallbackQuery):
    order_id = int(callback.data.replace("accept_", ""))
    ok = await accept_order(order_id, callback.from_user.id)
    if not ok:
        await callback.answer("Bu buyurtma allaqachon olingan yoki topilmadi", show_alert=True)
        return

    order = await get_order(order_id)
    await callback.message.edit_text(
        f"✅ Buyurtma №{order_id} sizga biriktirildi!\n\n"
        f"📦 {order['product_name']}\n"
        f"👤 {order['user_name']}\n"
        f"📍 Lokatsiya yuborilgan.",
        reply_markup=courier_active_kb(order_id)
    )
    await callback.answer("Qabul qilindi!")

    # Mijozga xabar
    try:
        await bot.send_message(
            order["user_tg_id"],
            f"🚚 Buyurtma №{order_id} kuryer tomonidan qabul qilindi.\n"
            f"Tez orada yetkazib beriladi."
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("delivering_"))
async def set_delivering(callback: CallbackQuery):
    order_id = int(callback.data.replace("delivering_", ""))
    await update_order_status(order_id, "delivering")
    order = await get_order(order_id)
    await callback.message.edit_text(
        f"🚚 Buyurtma №{order_id} yetkazilmoqda...",
        reply_markup=courier_active_kb(order_id)
    )
    await callback.answer()
    try:
        await bot.send_message(order["user_tg_id"], f"🚚 Buyurtma №{order_id} yo'lda!")
    except Exception:
        pass


@dp.callback_query(F.data.startswith("delivered_"))
async def set_delivered(callback: CallbackQuery):
    order_id = int(callback.data.replace("delivered_", ""))
    await update_order_status(order_id, "delivered")
    order = await get_order(order_id)
    await callback.message.edit_text(
        f"✅ Buyurtma №{order_id} muvaffaqiyatli yetkazib berildi!",
        reply_markup=back_main_kb()
    )
    await callback.answer("Yaxshi ish!")
    try:
        await bot.send_message(
            order["user_tg_id"],
            f"✅ Buyurtma №{order_id} yetkazib berildi. Rahmat! 🛍"
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("map_"))
async def show_map(callback: CallbackQuery):
    order_id = int(callback.data.replace("map_", ""))
    order = await get_order(order_id)
    if order:
        await bot.send_location(callback.from_user.id, order["lat"], order["lon"])
    await callback.answer()


# ========== MENING BUYURTMALARIM ==========
@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    orders = await get_user_orders(callback.from_user.id)
    if not orders:
        await callback.message.edit_text(
            "Sizda hali buyurtma yo'q.",
            reply_markup=back_main_kb()
        )
        await callback.answer()
        return

    text = "📦 <b>Sizning buyurtmalaringiz:</b>\n\n"
    for o in orders[:15]:
        status_emoji = {
            "new": "🆕", "accepted": "✅", "delivering": "🚚",
            "delivered": "🏁", "cancelled": "❌"
        }.get(o["status"], "•")
        text += (
            f"{status_emoji} №{o['id']} — {o['product_name'][:25]}\n"
            f"   {format_price(o['total_price'])} · {o['status']}\n\n"
        )
    await callback.message.edit_text(text, reply_markup=back_main_kb())
    await callback.answer()


# ========== ADMIN PANEL ==========
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    new_orders = await get_new_orders()
    products = await get_all_products()
    active_count = sum(1 for p in products if p["is_active"])
    text = (
        f"⚙️ <b>Admin panel</b>\n\n"
        f"🆕 Yangi buyurtmalar: {len(new_orders)} ta\n"
        f"📦 Jami mahsulotlar: {len(products)} ta ({active_count} faol)\n\n"
        f"Quyidagilardan birini tanlang:"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Mahsulotlarni boshqarish", callback_data="admin_products")
    builder.button(text="➕ Mahsulot qo'shish", callback_data="add_product")
    builder.button(text="⬅️ Bosh menyu", callback_data="back_main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    products = await get_all_products()
    if not products:
        await callback.message.edit_text(
            "Hozircha mahsulot yo'q.",
            reply_markup=back_main_kb()
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for p in products[:40]:
        status = "✅" if p["is_active"] else "❌"
        builder.button(
            text=f"{status} {p['name'][:28]} — {p['price']}",
            callback_data=f"admin_prod_{p['id']}"
        )
    builder.button(text="⬅️ Orqaga", callback_data="admin_panel")
    builder.adjust(1)
    await callback.message.edit_text(
        f"📦 <b>Mahsulotlar ro'yxati</b> ({len(products)} ta)\n"
        f"Mahsulotni tanlang (tahrirlash / o'chirish):",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_prod_"))
async def admin_product_detail(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    product_id = int(callback.data.replace("admin_prod_", ""))
    product = await get_product(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    status = "Faol ✅" if product["is_active"] else "O'chirilgan ❌"
    text = (
        f"<b>{product['name']}</b>\n\n"
        f"{product['description'] or 'Tavsif yo‘q'}\n\n"
        f"💰 Narxi: {format_price(product['price'])}\n"
        f"📂 {category_name(product['category'])}\n"
        f"Holat: {status}\n"
        f"ID: {product['id']}"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Nomini o'zgartirish", callback_data=f"edit_name_{product_id}")
    builder.button(text="💰 Narxini o'zgartirish", callback_data=f"edit_price_{product_id}")
    builder.button(text="📝 Tavsifini o'zgartirish", callback_data=f"edit_desc_{product_id}")
    if product["is_active"]:
        builder.button(text="🗑 O'chirish (yashirish)", callback_data=f"del_prod_{product_id}")
    else:
        builder.button(text="✅ Qayta faollashtirish", callback_data=f"act_prod_{product_id}")
    builder.button(text="⬅️ Orqaga", callback_data="admin_products")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data.startswith("del_prod_"))
async def delete_product_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    product_id = int(callback.data.replace("del_prod_", ""))
    await deactivate_product(product_id)
    await callback.answer("Mahsulot yashirildi (o'chirildi)", show_alert=True)
    # Qayta ko'rsatish
    product = await get_product(product_id)
    status = "O'chirilgan ❌"
    text = (
        f"<b>{product['name']}</b>\n\n"
        f"💰 Narxi: {format_price(product['price'])}\n"
        f"Holat: {status}\n"
        f"ID: {product['id']}"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qayta faollashtirish", callback_data=f"act_prod_{product_id}")
    builder.button(text="⬅️ Orqaga", callback_data="admin_products")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("act_prod_"))
async def activate_product_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    product_id = int(callback.data.replace("act_prod_", ""))
    await activate_product(product_id)
    await callback.answer("Mahsulot qayta faollashtirildi", show_alert=True)
    product = await get_product(product_id)
    status = "Faol ✅"
    text = (
        f"<b>{product['name']}</b>\n\n"
        f"💰 Narxi: {format_price(product['price'])}\n"
        f"Holat: {status}\n"
        f"ID: {product['id']}"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 O'chirish (yashirish)", callback_data=f"del_prod_{product_id}")
    builder.button(text="⬅️ Orqaga", callback_data="admin_products")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ========== MAHSULOT TAHRIRLASH ==========
@dp.callback_query(F.data.startswith("edit_name_"))
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    product_id = int(callback.data.replace("edit_name_", ""))
    await state.update_data(edit_product_id=product_id, edit_field="name")
    await state.set_state(EditProduct.waiting_value)
    await callback.message.answer("Yangi nomni yozing:")
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_price_"))
async def edit_price_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    product_id = int(callback.data.replace("edit_price_", ""))
    await state.update_data(edit_product_id=product_id, edit_field="price")
    await state.set_state(EditProduct.waiting_value)
    await callback.message.answer("Yangi narxni yozing (faqat raqam):")
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_desc_"))
async def edit_desc_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    product_id = int(callback.data.replace("edit_desc_", ""))
    await state.update_data(edit_product_id=product_id, edit_field="description")
    await state.set_state(EditProduct.waiting_value)
    await callback.message.answer("Yangi tavsifni yozing:")
    await callback.answer()


@dp.message(EditProduct.waiting_value)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["edit_product_id"]
    field = data["edit_field"]
    value = message.text.strip()

    if field == "price":
        try:
            value = int(value.replace(" ", "").replace(",", ""))
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Noto'g'ri narx. Faqat musbat raqam yozing:")
            return
        await update_product(product_id, price=value)
    elif field == "name":
        await update_product(product_id, name=value)
    elif field == "description":
        await update_product(product_id, description=value)

    await state.clear()
    product = await get_product(product_id)
    await message.answer(
        f"✅ Yangilandi!\n\n"
        f"<b>{product['name']}</b>\n"
        f"💰 {format_price(product['price'])}\n"
        f"{product['description'] or ''}",
        reply_markup=back_main_kb()
    )


@dp.message(Command("setrole"))
async def set_role(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Format: /setrole TELEGRAM_ID role")
        return
    try:
        tg_id = int(parts[1])
        role = parts[2].lower()
        if role not in ("admin", "mahsulotchi", "courier", "customer"):
            raise ValueError
        await get_or_create_user(tg_id)
        from database import update_user_role
        await update_user_role(tg_id, role)
        await message.answer(f"✅ {tg_id} → {role}")
    except Exception:
        await message.answer("Xato. Format: /setrole 123456789 courier")


# Deep link: /start prod_123
@dp.message(CommandStart(deep_link=True))
async def deep_start(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("prod_"):
        try:
            product_id = int(args[1].replace("prod_", ""))
            product = await get_product(product_id)
            if product:
                caption = (
                    f"<b>{product['name']}</b>\n\n"
                    f"{product['description'] or ''}\n\n"
                    f"💰 Narxi: <b>{format_price(product['price'])}</b>\n"
                    f"📂 {category_name(product['category'])}"
                )
                await message.answer_photo(
                    photo=product["photo_file_id"],
                    caption=caption,
                    reply_markup=product_kb(product_id)
                )
                return
        except Exception:
            pass
    await cmd_start(message, state)


async def main():
    await init_db()
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
