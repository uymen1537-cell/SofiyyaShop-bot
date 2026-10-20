import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Admin Telegram ID lari (vergul bilan ajratilgan)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()]

# Mahsulot qo'shuvchilar (mahsulotchi)
MAHSULOTCHI_IDS = [int(x) for x in os.getenv("MAHSULOTCHI_IDS", "").split(",") if x.strip()]

# Kuryerlar
COURIER_IDS = [int(x) for x in os.getenv("COURIER_IDS", "").split(",") if x.strip()]

# Kanal ID (masalan: -1001234567890). Bot kanalda admin bo'lishi kerak!
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# Do'kon lokatsiyasi (Toshkent markazi misol uchun)
SHOP_LAT = float(os.getenv("SHOP_LAT", "41.311151"))
SHOP_LON = float(os.getenv("SHOP_LON", "69.279737"))

# Yetkazib berish narxlari (so'm)
DELIVERY_PRICE_PER_KM = int(os.getenv("DELIVERY_PRICE_PER_KM", "3000"))  # 1 km uchun
MIN_DELIVERY_PRICE = int(os.getenv("MIN_DELIVERY_PRICE", "15000"))      # minimal
MAX_DELIVERY_KM = float(os.getenv("MAX_DELIVERY_KM", "25"))             # max masofa

# Taxminiy yetkazib berish vaqti (daqiqa)
EST_TIME_MAVJUD = 60          # mavjud mahsulot
EST_TIME_YOLDA = 180          # yo'lda
EST_TIME_BUYURTMA = 1440      # buyurtma asosida (1 kun)

DB_PATH = "sofiyya_shop.db"
