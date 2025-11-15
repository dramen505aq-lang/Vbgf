from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
import json
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image

# إعدادات التليجرام
TELEGRAM_BOT_TOKEN = '8496420855:AAH8uWYrugWuYJtemwxzRcGnGSP1elO-m5U'
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'

# إعداد الساعات المتاحة
AVAILABLE_WATCHES = {
    "رولكس ديت": {"price": 16700, "category": "فاخرة"},
    "هلال الرقمية": {"price": 11500, "category": "رقمية"},
    "رادو مستر كوالتي": {"price": 27900, "category": "فاخرة"},
    "كارتير الرجالية": {"price": 16700, "category": "كلاسيكية"},
    "أوميغا الرجالية": {"price": 39000, "category": "فاخرة"},
    "أوميغا النسائية": {"price": 39000, "category": "فاخرة"},
    "Viokai مروحة السباق": {"price": 11700, "category": "رياضية"},
    "هلال الجلد": {"price": 11500, "category": "كلاسيكية"}
}

app = Flask(__name__)
CORS(app)

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_chat_id():
    """الحصول على chat_id من آخر تحديث"""
    try:
        updates_url = f"{TELEGRAM_API_URL}/getUpdates"
        updates_response = requests.get(updates_url)
        updates_data = updates_response.json()
        
        if updates_data.get('ok') and updates_data.get('result'):
            return updates_data['result'][-1]['message']['chat']['id']
        return None
    except Exception as e:
        logger.error(f"خطأ في الحصول على chat_id: {e}")
        return None

def validate_watch_order(cart):
    """التحقق من صحة الساعات في الطلب"""
    valid_items = []
    invalid_items = []
    
    for item in cart:
        watch_name = item.get('name', '')
        
        # البحث عن الساعة في القائمة
        found_watch = None
        for watch_key, watch_info in AVAILABLE_WATCHES.items():
            if watch_key in watch_name:
                found_watch = watch_key
                break
        
        if found_watch:
            # تحديث السعر إذا كان مختلفاً
            correct_price = AVAILABLE_WATCHES[found_watch]["price"]
            if item.get('price') != correct_price:
                item['price'] = correct_price
                item['original_price'] = item.get('price')
            
            valid_items.append(item)
        else:
            invalid_items.append(watch_name)
    
    return valid_items, invalid_items

def create_order_message(order_data):
    """إنشاء رسالة الطلب"""
    customer = order_data['customer']
    cart = order_data['cart']
    total = order_data['total']
    
    message = "🛒 *طلب جديد من متجر أوڤو*\n\n"
    message += f"👤 *اسم المشتري:* {customer['name']}\n"
    message += f"📞 *رقم الهاتف:* {customer['phone']}\n"
    message += f"📍 *المحافظة:* {customer['province']}\n"
    message += f"🏘️ *المديرية:* {customer['district']}\n"
    message += f"🗺️ *المنطقة:* {customer.get('area', 'غير محدد')}\n"
    message += f"🎨 *اللون:* {customer.get('color', 'غير محدد')}\n"
    message += f"📝 *ملاحظات:* {customer.get('notes', 'لا يوجد')}\n\n"
    
    message += "🛍️ *الطلبيات:*\n"
    for item in cart:
        item_total = item['price'] * item['quantity']
        message += f"• *{item['name']}*\n"
        message += f"  💰 السعر: {item['price']:,} ريال\n"
        message += f"  📦 الكمية: {item['quantity']}\n"
        message += f"  🏷️ المجموع: {item_total:,} ريال\n\n"
    
    message += f"💰 *المجموع الكلي:* {total:,} ريال\n\n"
    message += f"⏰ *وقت الطلب:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message

def send_to_bot_owner(text):
    """إرسال رسالة إلى البوت"""
    chat_id = get_chat_id()
    if not chat_id:
        return False, "لا يمكن العثور على chat_id"
    
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True, "تم إرسال الرسالة"
    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
        return False, f"خطأ في الإرسال: {e}"

def send_photo_to_bot_owner(photo_url, caption=""):
    """إرسال صورة إلى البوت"""
    chat_id = get_chat_id()
    if not chat_id:
        return False, "لا يمكن العثور على chat_id"
    
    url = f"{TELEGRAM_API_URL}/sendPhoto"
    payload = {
        'chat_id': chat_id,
        'photo': photo_url,
        'caption': caption,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True, "تم إرسال الصورة"
    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في إرسال الصورة: {e}")
        return False, f"خطأ في إرسال الصورة: {e}"

def send_base64_photo_to_bot_owner(base64_data, caption=""):
    """إرسال صورة base64 إلى البوت"""
    chat_id = get_chat_id()
    if not chat_id:
        return False, "لا يمكن العثور على chat_id"
    
    url = f"{TELEGRAM_API_URL}/sendPhoto"
    
    try:
        # تحويل base64 إلى bytes
        if base64_data.startswith('data:image'):
            base64_data = base64_data.split(',')[1]
        
        image_data = base64.b64decode(base64_data)
        
        # إرسال الصورة كملف
        files = {'photo': ('product.jpg', image_data, 'image/jpeg')}
        data = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, files=files, data=data, timeout=30)
        response.raise_for_status()
        return True, "تم إرسال الصورة"
    except Exception as e:
        logger.error(f"خطأ في إرسال صورة base64: {e}")
        return False, f"خطأ في إرسال الصورة: {e}"

@app.route('/send_order', methods=['POST', 'OPTIONS'])
def send_order():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # استقبال بيانات الطلب
        order_data = request.get_json()
        logger.info(f"استقبال طلب جديد من: {order_data.get('customer', {}).get('name', 'غير معروف')}")
        
        if not order_data:
            return jsonify({'success': False, 'message': 'لا توجد بيانات'}), 400
        
        # التحقق من صحة الساعات
        valid_cart, invalid_items = validate_watch_order(order_data['cart'])
        
        if invalid_items:
            logger.warning(f"ساعات غير معروفة: {invalid_items}")
        
        if not valid_cart:
            return jsonify({'success': False, 'message': 'لا توجد عناصر صالحة في الطلب'}), 400
        
        # تحديث بيانات الطلب بالسلات الصحيحة
        order_data['cart'] = valid_cart
        
        # إنشاء رسالة الطلب
        message = create_order_message(order_data)
        
        # إرسال الرسالة النصية إلى البوت
        success, result_message = send_to_bot_owner(message)
        
        # إرسال الصور
        images_sent = 0
        for item in valid_cart:
            if item.get('image_base64'):
                # إرسال الصورة كـ base64
                photo_caption = f"📸 {item['name']}"
                photo_success, photo_message = send_base64_photo_to_bot_owner(
                    item['image_base64'], 
                    photo_caption
                )
                if photo_success:
                    images_sent += 1
                    logger.info(f"تم إرسال صورة: {item['name']}")
                else:
                    logger.error(f"فشل إرسال صورة: {item['name']} - {photo_message}")
            
            elif item.get('image_url'):
                # إرسال الصورة كرابط
                photo_caption = f"📸 {item['name']}"
                photo_success, photo_message = send_photo_to_bot_owner(
                    item['image_url'], 
                    photo_caption
                )
                if photo_success:
                    images_sent += 1
                    logger.info(f"تم إرسال صورة: {item['name']}")
                else:
                    logger.error(f"فشل إرسال صورة: {item['name']} - {photo_message}")
        
        # إرسال تنبيه إذا كانت هناك ساعات غير معروفة
        if invalid_items:
            alert_message = f"⚠️ *تنبيه:* هناك ساعات غير معروفة في الطلب:\n{', '.join(invalid_items)}"
            send_to_bot_owner(alert_message)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'{result_message} - تم إرسال {images_sent} صورة',
                'valid_items': len(valid_cart),
                'images_sent': images_sent,
                'invalid_items': invalid_items
            })
        else:
            return jsonify({
                'success': False,
                'message': result_message
            }), 500
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الطلب: {e}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ في الخادم: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'Ouvow Watch Store API'})

if __name__ == '__main__':
    logger.info("بدء تشغيل خادم متجر أوڤو...")
    app.run(host='0.0.0.0', port=5000, debug=True)
