# 🛍 SofiyyaShop Telegram Bot

To'liq ishlaydigan Telegram do'kon boti:
- Admin / Mahsulotchi / Kuryer / Mijoz rollari
- Mahsulot qo'shish (nom, tavsif, rasm, narx, kategoriya) → avtomatik kanalga joylash
- 3 kategoriya: **Mavjud**, **Yo'lda**, **Buyurtma asosida**
- Sotib olish + lokatsiya orqali yetkazib berish
- Masofa bo'yicha avtomatik yetkazib berish narxi (Haversine)
- Kuryer paneli: buyurtmani qabul qilish, yetkazish, yakunlash

## O'rnatish

1. Python 3.10+ kerak.

```bash
cd sofiyyashop_bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. `.env` fayl yarating (`.env.example` dan nusxa oling):

```bash
cp .env.example .env
```

`.env` ni to'ldiring:

- `BOT_TOKEN` — @BotFather dan olingan token
- `ADMIN_IDS` — sizning Telegram ID (vergul bilan bir nechta)
- `MAHSULOTCHI_IDS` — mahsulot qo'shadigan odamlar ID si
- `COURIER_IDS` — kuryerlar ID si
- `CHANNEL_ID` — kanal ID si (bot kanalda **admin** bo'lishi shart!)
- `SHOP_LAT` / `SHOP_LON` — do'koningiz koordinatalari
- yetkazib berish narxlari

Telegram ID ni bilish: @userinfobot ga yozing.

Kanal ID ni bilish: kanalga xabar yuboring, keyin `https://api.telegram.org/bot<TOKEN>/getUpdates` ga kiring.

3. Ishga tushirish:

```bash
python bot.py
```

## Foydalanish

### Mijoz
- `/start` → Katalog → kategoriya → mahsulot → Sotib olish
- Miqdor → lokatsiya yuborish → narx hisoblanadi → tasdiqlash

### Mahsulotchi / Admin
- "➕ Mahsulot qo'shish" tugmasi
- Nom → Tavsif → Rasm → Narx → Kategoriya
- Avtomatik kanalga post tashlanadi + "Sotib olish" tugmasi

### Kuryer
- "🚚 Kuryer paneli"
- Yangi buyurtmalarni ko'radi, qabul qiladi, yetkazadi

### Admin buyruqlar
```
/setrole TELEGRAM_ID role
```
role: `admin` | `mahsulotchi` | `courier` | `customer`

## Eslatmalar

- Bot kanalda admin bo'lishi kerak (post yuborish uchun).
- Lokatsiya Telegram xarita orqali aniq olinadi.
- Yetkazib berish narxi: `max(MIN_DELIVERY_PRICE, masofa_km * DELIVERY_PRICE_PER_KM)`
- Kod ixcham, SQLite ishlatiladi, qo'shimcha server shart emas.

Savollar bo'lsa yozing!
