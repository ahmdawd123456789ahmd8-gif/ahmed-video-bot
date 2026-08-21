import telebot
from telebot import types
import time
import os
import sys
import yt_dlp
import threading
import re
import math
import hashlib
from datetime import datetime, timedelta
import random
import pytz

# ============================================
# 🔐 قراءة التوكن من متغيرات البيئة
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 8460989245))

# التحقق من وجود التوكن
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Please set it in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)

# قاعدة بيانات للمستخدمين
users_db = set()
user_states = {}

# تخزين مؤقت للروابط
temp_links = {}

# تخزين معرفات الرسائل النصية فقط للحذف
user_messages = {}

# تخزين عمليات التحميل النشطة
active_downloads = {}

# تخزين بيانات التحميل للإيقاف
download_processes = {}

# ملفات الكوكيز
COOKIE_FILES = {
    'youtube': 'cookies_youtube.txt',
    'instagram': 'cookies_instagram.txt',
    'facebook': 'cookies_facebook.txt',
    'tiktok': 'cookies_tiktok.txt'
}

# حدود حجم الملفات
MAX_VIDEO_SIZE = 50000000
CHUNK_SIZE = 50 * 1024 * 1024

# أسماء المنصات بالعربي
PLATFORM_NAMES = {
    'youtube': 'يوتيوب',
    'instagram': 'انستغرام',
    'facebook': 'فيسبوك',
    'tiktok': 'تيك توك'
}

# رموز أنميشن للحذف
DELETE_ANIMATIONS = [
    "🗑️ ❌",
    "🗑️ ❌❌",
    "🗑️ ❌❌❌",
    "🗑️ ✨",
    "🗑️ 💫",
    "🗑️ ⚡",
    "🗑️ 🔥",
    "🗑️ 💥",
]

# تعيين الأوامر
def set_bot_commands():
    try:
        commands = [
            types.BotCommand("start", "🎬 ابدأ التحميل"),
            types.BotCommand("admin", "🔐 لوحة المطور"),
            types.BotCommand("cookies", "🍪 إدارة الكوكيز"),
            types.BotCommand("checkcookies", "🔍 التحقق من الكوكيز"),
            types.BotCommand("deletecookies", "🗑️ حذف الكوكيز"),
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Error: {e}")

set_bot_commands()

# دالة لتحديد المنصة من الرابط
def get_platform_from_url(url):
    if not url:
        return None
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'instagram.com' in url or 'instagr.am' in url:
        return 'instagram'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'facebook'
    elif 'tiktok.com' in url:
        return 'tiktok'
    return None

# دالة استخراج كوكيز انستغرام فقط
def extract_instagram_cookies(cookies_text):
    lines = cookies_text.split('\n')
    insta_lines = []
    insta_lines.append("# Netscape HTTP Cookie File")
    
    for line in lines:
        if 'instagram.com' in line and not line.startswith('#'):
            parts = line.split('\t')
            if len(parts) >= 7:
                insta_lines.append(line)
            elif ' ' in line:
                parts = line.split(' ')
                if len(parts) >= 7:
                    insta_lines.append('\t'.join(parts))
    
    return '\n'.join(insta_lines)

# دالة لحفظ الكوكيز من نص
def save_cookies_from_text(platform, cookies_text):
    try:
        filename = COOKIE_FILES.get(platform)
        if not filename:
            return False
        
        if platform == 'instagram':
            cookies_text = extract_instagram_cookies(cookies_text)
            if len(cookies_text.split('\n')) < 3:
                return False
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(cookies_text)
        print(f"✅ {platform} cookies saved successfully!")
        return True
    except Exception as e:
        print(f"❌ Error saving {platform} cookies: {e}")
        return False

# دالة لحفظ الكوكيز من ملف
def save_cookies_from_file(platform, file_content):
    try:
        filename = COOKIE_FILES.get(platform)
        if not filename:
            return False
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8', errors='ignore')
        
        if platform == 'instagram':
            file_content = extract_instagram_cookies(file_content)
            if len(file_content.split('\n')) < 3:
                return False
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(file_content)
        print(f"✅ {platform} cookies saved from file successfully!")
        return True
    except Exception as e:
        print(f"❌ Error saving {platform} cookies from file: {e}")
        return False

# دالة لقراءة الكوكيز
def load_cookies(platform):
    try:
        filename = COOKIE_FILES.get(platform)
        if not filename:
            return None
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    except Exception as e:
        print(f"❌ Error loading {platform} cookies: {e}")
        return None

# دالة للتحقق من وجود كوكيز للمنصة
def has_cookies(platform):
    if not platform:
        return False
    filename = COOKIE_FILES.get(platform)
    if not filename:
        return False
    return os.path.exists(filename) and os.path.getsize(filename) > 0

# دالة لحذف كوكيز منصة
def delete_cookies(platform):
    try:
        filename = COOKIE_FILES.get(platform)
        if not filename:
            return False
        if os.path.exists(filename):
            os.remove(filename)
            print(f"🗑️ {platform} cookies deleted!")
            return True
        return False
    except Exception as e:
        print(f"❌ Error deleting {platform} cookies: {e}")
        return False

# دالة لحذف جميع الكوكيز
def delete_all_cookies():
    count = 0
    for platform, filename in COOKIE_FILES.items():
        if os.path.exists(filename):
            try:
                os.remove(filename)
                count += 1
                print(f"🗑️ {platform} cookies deleted!")
            except:
                pass
    return count

# دالة لحذف الرسائل النصية فقط مع أنميشن
def delete_user_messages(user_id, keep_last=None):
    if user_id not in user_messages:
        return
    
    messages = user_messages[user_id]
    
    if user_id in active_downloads and active_downloads[user_id]:
        return
    
    if keep_last is not None and keep_last > 0:
        messages = messages[:-keep_last]
    
    for i, msg_id in enumerate(messages):
        try:
            if i % 2 == 0:
                animation = random.choice(DELETE_ANIMATIONS)
                try:
                    bot.edit_message_text(
                        f"{animation} جاري الحذف...",
                        chat_id=user_id,
                        message_id=msg_id
                    )
                except:
                    pass
                time.sleep(0.15)
            
            bot.delete_message(user_id, msg_id)
            time.sleep(0.05)
        except:
            pass
    
    if keep_last is not None and keep_last > 0:
        user_messages[user_id] = user_messages[user_id][-keep_last:]
    else:
        user_messages[user_id] = []

# دالة لإضافة رسالة نصية للحذف
def add_user_message(user_id, message_id):
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message_id)
    if len(user_messages[user_id]) > 50:
        user_messages[user_id] = user_messages[user_id][-50:]

# دالة لتوليد معرف قصير للرابط
def generate_short_id(url):
    hash_obj = hashlib.md5(f"{url}_{time.time()}".encode())
    return hash_obj.hexdigest()[:10]

# دالة لتنسيق الوقت
def format_time(seconds):
    if seconds < 60:
        return f"{int(seconds)} ثانية"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes} دقيقة {secs} ثانية"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} ساعة {minutes} دقيقة"

# دالة لتنسيق الحجم
def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    else:
        return f"{size_bytes / (1024*1024*1024):.2f} GB"

# دالة لعرض شريط تقدم محسن مع تحديث دقيق
def get_progress_bar(percent, width=20):
    filled = int(width * percent / 100)
    if filled > width:
        filled = width
    bar = '█' * filled + '░' * (width - filled)
    return bar

# دالة لإيقاف التحميل
def stop_download(user_id, download_id):
    if user_id in download_processes and download_processes[user_id] == download_id:
        if user_id in active_downloads and active_downloads[user_id] == download_id:
            try:
                for file in os.listdir('.'):
                    if file.startswith(f'download_{user_id}_'):
                        os.remove(file)
                        print(f"🗑️ تم حذف الملف المؤقت: {file}")
            except:
                pass
            
            del active_downloads[user_id]
            if user_id in download_processes:
                del download_processes[user_id]
            
            return True
    return False

# ============================================
# 🔥 دالة العداد مع تحديث شريط التحميل بشكل دقيق
# ============================================
def update_download_timer(user_id, message_id, progress_data, media_type, download_id):
    seconds = 0
    last_update_time = 0
    last_percent = -1
    
    BISMILLAH = "﴿بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ﴾"
    
    SURAH_IKHLAS = (
        "﴿قُلْ هُوَ اللَّهُ أَحَدٌ ۝ اللَّهُ الصَّمَدُ ۝ لَمْ يَلِدْ وَلَمْ يُولَدْ ۝ وَلَمْ يَكُنْ لَهُ كُفُوًا أَحَدٌ﴾"
    )
    
    AYAT_AL_KURSI = (
        "﴿اللَّهُ لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ ۝ لَا تَأْخُذُهُ سِنَةٌ وَلَا نَوْمٌ ۝ لَهُ مَا فِي السَّمَاوَاتِ وَمَا فِي الْأَرْضِ ۝ مَنْ ذَا الَّذِي يَشْفَعُ عِنْدَهُ إِلَّا بِإِذْنِهِ ۝ يَعْلَمُ مَا بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ ۝ وَلَا يُحِيطُونَ بِشَيْءٍ مِنْ عِلْمِهِ إِلَّا بِمَا شَاءَ ۝ وَسِعَ كُرْسِيُّهُ السَّمَاوَاتِ وَالْأَرْضَ ۝ وَلَا يَئُودُهُ حِفْظُهُمَا ۝ وَهُوَ الْعَلِيُّ الْعَظِيمُ﴾"
    )
    
    SURAH_BAQARAH_END = (
        "﴿لِلَّهِ مَا فِي السَّمَاوَاتِ وَمَا فِي الْأَرْضِ ۝ وَإِنْ تُبْدُوا مَا فِي أَنْفُسِكُمْ أَوْ تُخْفُوهُ يُحَاسِبْكُمْ بِهِ اللَّهُ ۝ فَيَغْفِرُ لِمَنْ يَشَاءُ وَيُعَذِّبُ مَنْ يَشَاءُ ۝ وَاللَّهُ عَلَى كُلِّ شَيْءٍ قَدِيرٌ ۝ آمَنَ الرَّسُولُ بِمَا أُنْزِلَ إِلَيْهِ مِنْ رَبِّهِ وَالْمُؤْمِنُونَ ۝ كُلٌّ آمَنَ بِاللَّهِ وَمَلَائِكَتِهِ وَكُتُبِهِ وَرُسُلِهِ ۝ لَا نُفَرِّقُ بَيْنَ أَحَدٍ مِنْ رُسُلِهِ ۝ وَقَالُوا سَمِعْنَا وَأَطَعْنَا ۝ غُفْرَانَكَ رَبَّنَا وَإِلَيْكَ الْمَصِيرُ ۝ لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا ۝ لَهَا مَا كَسَبَتْ وَعَلَيْهَا مَا اكْتَسَبَتْ ۝ رَبَّنَا لَا تُؤَاخِذْنَا إِنْ نَسِينَا أَوْ أَخْطَأْنَا ۝ رَبَّنَا وَلَا تَحْمِلْ عَلَيْنَا إِصْرًا كَمَا حَمَلْتَهُ عَلَى الَّذِينَ مِنْ قَبْلِنَا ۝ رَبَّنَا وَلَا تُحَمِّلْنَا مَا لَا طَاقَةَ لَنَا بِهِ ۝ وَاعْفُ عَنَّا وَاغْفِرْ لَنَا وَارْحَمْنَا ۝ أَنْتَ مَوْلَانَا فَانْصُرْنَا عَلَى الْقَوْمِ الْكَافِرِينَ﴾"
    )
    
    while not progress_data.get('stop', False):
        time.sleep(0.2)
        seconds += 0.2
        
        if progress_data.get('stop', False):
            break
            
        if user_id not in active_downloads or active_downloads[user_id] != download_id:
            break
            
        try:
            downloaded = progress_data.get('downloaded', 0)
            total = progress_data.get('total', 1)
            speed = progress_data.get('speed', 0)
            
            percent = (downloaded / total) * 100 if total > 0 else 0
            percent = min(percent, 100)
            
            current_time = time.time()
            if current_time - last_update_time >= 0.3 or abs(percent - last_percent) >= 0.5:
                last_update_time = current_time
                last_percent = percent
                
                bar = get_progress_bar(percent)
                
                if percent < 25:
                    color = '🔴'
                elif percent < 50:
                    color = '🟠'
                elif percent < 75:
                    color = '🟡'
                else:
                    color = '🟢'
                
                eta_text = "جاري الحساب..."
                remaining_time = 0
                if speed > 0 and total > downloaded:
                    remaining_time = (total - downloaded) / speed
                    eta_text = format_time(remaining_time)
                
                speed_text = format_size(speed) + "/ث" if speed > 0 else "جاري الحساب..."
                
                remaining_seconds = remaining_time if remaining_time > 0 else 0
                
                if remaining_seconds < 60:
                    quran_text = f"{BISMILLAH}\n\n{AYAT_AL_KURSI}\n\n{BISMILLAH}\n\n{SURAH_IKHLAS}"
                elif remaining_seconds < 120:
                    quran_text = f"{BISMILLAH}\n\n{AYAT_AL_KURSI}"
                else:
                    quran_text = f"{BISMILLAH}\n\n{SURAH_BAQARAH_END}"
                
                stop_markup = types.InlineKeyboardMarkup()
                stop_btn = types.InlineKeyboardButton(
                    "⏹️ إيقاف التحميل", 
                    callback_data=f"stop_{download_id}"
                )
                stop_markup.add(stop_btn)
                
                percent_display = f"{percent:.1f}"
                if percent >= 99.9:
                    percent_display = "99.9"
                
                status_text = (
                    f"📥 **تحميل {media_type}**\n\n"
                    f"┌─────────────────────────────────────┐\n"
                    f"│      {color} {bar} {color}      │\n"
                    f"└─────────────────────────────────────┘\n"
                    f"          **{percent_display}%**\n\n"
                    f"{quran_text}\n\n"
                    f"⏱️ **المدة:** {format_time(int(seconds))}\n"
                    f"📦 **الحجم:** {format_size(downloaded)} / {format_size(total)}\n"
                    f"⚡ **السرعة:** {speed_text}\n"
                    f"⏳ **المتبقي:** {eta_text}"
                )
                
                try:
                    bot.edit_message_text(
                        status_text,
                        chat_id=user_id,
                        message_id=message_id,
                        parse_mode='Markdown',
                        reply_markup=stop_markup
                    )
                except:
                    pass
                    
        except Exception as e:
            print(f"Timer error: {e}")
            break

# دالة لتقسيم الملف الكبير
def split_file(file_path, chunk_size=CHUNK_SIZE):
    parts = []
    file_size = os.path.getsize(file_path)
    num_chunks = math.ceil(file_size / chunk_size)
    
    with open(file_path, 'rb') as f:
        for i in range(num_chunks):
            part_path = f"{file_path}.part{i+1}"
            with open(part_path, 'wb') as part_file:
                chunk = f.read(chunk_size)
                part_file.write(chunk)
            parts.append(part_path)
    
    return parts, num_chunks

# دالة لإرسال الملف
def send_file(user_id, file_path, is_video=True):
    try:
        file_size = os.path.getsize(file_path)
        
        if file_size <= MAX_VIDEO_SIZE:
            with open(file_path, 'rb') as f:
                if is_video:
                    bot.send_video(user_id, f, caption="✅ تم التحميل بنجاح!", timeout=300)
                else:
                    bot.send_audio(user_id, f, caption="✅ تم التحميل بنجاح!", timeout=300)
            return True
        
        bot.send_message(user_id, f"📦 الملف كبير ({format_size(file_size)})، جاري التقسيم...")
        
        parts, num_chunks = split_file(file_path)
        
        info = f"📁 الملف مقسم إلى {num_chunks} أجزاء:\n\n"
        for i, part in enumerate(parts, 1):
            part_size = os.path.getsize(part)
            info += f"📎 الجزء {i}: {format_size(part_size)}\n"
        bot.send_message(user_id, info)
        
        for i, part in enumerate(parts, 1):
            with open(part, 'rb') as f:
                bot.send_document(
                    user_id, 
                    f,
                    caption=f"📎 الجزء {i} من {num_chunks}",
                    timeout=300
                )
            os.remove(part)
            time.sleep(0.5)
        
        bot.send_message(
            user_id, 
            f"✅ تم إرسال جميع الأجزاء بنجاح!\n💡 لدمجها: استخدم برنامج 7-Zip أو WinRAR"
        )
        return True
        
    except Exception as e:
        bot.send_message(user_id, f"❌ خطأ في الإرسال: {str(e)}")
        return False

# ============================================
# 📥 دالة التحميل الرئيسية (تم إصلاحها)
# ============================================
def download_with_progress(user_id, message_id, url, is_video, media_type, download_id):
    progress_data = {
        'stop': False,
        'downloaded': 0,
        'total': 1,
        'speed': 0,
        'start_time': time.time()
    }
    
    timer_thread = threading.Thread(
        target=update_download_timer,
        args=(user_id, message_id, progress_data, media_type, download_id)
    )
    timer_thread.daemon = True
    timer_thread.start()
    
    def progress_hook(d):
        if user_id in active_downloads and active_downloads[user_id] != download_id:
            progress_data['stop'] = True
            return
            
        if d['status'] == 'downloading':
            downloaded_bytes = d.get('downloaded_bytes', 0)
            total_bytes = d.get('total_bytes', 1)
            
            progress_data['downloaded'] = downloaded_bytes
            progress_data['total'] = total_bytes if total_bytes > 0 else 1
            progress_data['speed'] = d.get('speed', 0)
            
        elif d['status'] == 'finished':
            progress_data['stop'] = True
            progress_data['downloaded'] = progress_data['total']
    
    # إعدادات yt-dlp الأساسية
    ydl_opts = {
        'outtmpl': f'download_{user_id}_{int(time.time())}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': True,
        'socket_timeout': 300,
        'retries': 10,
        'progress_hooks': [progress_hook],
    }
    
    platform = get_platform_from_url(url)
    
    # إضافة الكوكيز إذا وجدت
    if platform and has_cookies(platform):
        cookie_file = COOKIE_FILES.get(platform)
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            print(f"✅ Using {platform} cookies for user {user_id}")
    
    # ============================================
    # 🔧 إعدادات خاصة بالمنصات (معدلة - تم إصلاح الخطأ)
    # ============================================
    if platform == 'youtube':
        # إعدادات يوتيوب بدون skip_download
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip_download': ['false'],  # هذا الخيار للتأكد من التحميل
            }
        }
        # استخدام أفضل صيغة للفيديو
        if is_video:
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
    
    elif platform == 'instagram':
        ydl_opts['extractor_args'] = {
            'instagram': {
                'skip_download': ['false'],
            }
        }
        if is_video:
            ydl_opts['format'] = 'best[ext=mp4]/best'
        else:
            ydl_opts['format'] = 'bestaudio/best'
    
    elif platform == 'tiktok':
        ydl_opts['extractor_args'] = {
            'tiktok': {
                'embed': ['false'],
            }
        }
        if is_video:
            ydl_opts['format'] = 'best[ext=mp4]/best'
        else:
            ydl_opts['format'] = 'bestaudio/best'
    
    elif platform == 'facebook':
        ydl_opts['extractor_args'] = {
            'facebook': {
                'prefer_av1': ['false'],
            }
        }
        if is_video:
            ydl_opts['format'] = 'best[ext=mp4]/best'
        else:
            ydl_opts['format'] = 'bestaudio/best'
    
    else:
        # لأي منصة أخرى
        if is_video:
            ydl_opts['format'] = 'best[ext=mp4]/best'
        else:
            ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['extractor_args'] = {}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if user_id not in active_downloads or active_downloads[user_id] != download_id:
                raise Exception("تم إيقاف التحميل")
            
            filename = ydl.prepare_filename(info)
            
            # إذا كان الملف غير موجود، نحاول البحث عنه
            if not os.path.exists(filename):
                base_name = os.path.splitext(filename)[0]
                possible_extensions = ['.mp4', '.mp3', '.m4a', '.webm', '.opus', '.ogg']
                for ext in possible_extensions:
                    if os.path.exists(f"{base_name}{ext}"):
                        filename = f"{base_name}{ext}"
                        break
            
            progress_data['stop'] = True
            timer_thread.join(timeout=2)
            return filename
            
    except Exception as e:
        progress_data['stop'] = True
        if "تم إيقاف التحميل" in str(e):
            raise Exception("تم إيقاف التحميل")
        raise e

# ============================================
# 🎯 أمر البداية
# ============================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    users_db.add(user_id)
    
    welcome_text = (
        "✨ **مرحباً بك في بوت التحميل!**\n\n"
        "👇 اختر المنصة:"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_youtube = types.InlineKeyboardButton("▶️ يوتيوب", callback_data="platform_youtube")
    btn_insta = types.InlineKeyboardButton("📸 انستغرام", callback_data="platform_instagram")
    btn_facebook = types.InlineKeyboardButton("📘 فيسبوك", callback_data="platform_facebook")
    btn_tiktok = types.InlineKeyboardButton("🎵 تيك توك", callback_data="platform_tiktok")
    
    markup.add(btn_youtube, btn_insta)
    markup.add(btn_facebook, btn_tiktok)
    
    msg = bot.send_message(user_id, welcome_text, parse_mode='Markdown', reply_markup=markup)
    add_user_message(user_id, msg.message_id)

# ============================================
# 🔐 أمر الأدمن
# ============================================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "❌ هذا الأمر للمطور فقط")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_stats = types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")
    btn_broadcast = types.InlineKeyboardButton("📢 الإذاعة", callback_data="admin_broadcast")
    btn_cookies = types.InlineKeyboardButton("🍪 إدارة الكوكيز", callback_data="admin_cookies")
    btn_delete = types.InlineKeyboardButton("🗑️ حذف الكوكيز", callback_data="admin_delete")
    btn_info = types.InlineKeyboardButton("ℹ️ معلومات البوت", callback_data="admin_info")
    btn_restart = types.InlineKeyboardButton("🔄 إعادة تشغيل", callback_data="admin_restart")
    
    markup.add(btn_stats, btn_broadcast)
    markup.add(btn_cookies, btn_delete)
    markup.add(btn_info, btn_restart)
    
    msg = bot.send_message(
        ADMIN_ID,
        "🔐 **لوحة تحكم المطور**\n\nاختر الخدمة التي تريدها:",
        reply_markup=markup
    )
    add_user_message(ADMIN_ID, msg.message_id)

# ============================================
# 📝 أمر إدارة الكوكيز
# ============================================
@bot.message_handler(commands=['cookies'])
def manage_cookies(message):
    user_id = message.chat.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ هذا الأمر للمطور فقط")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_youtube = types.InlineKeyboardButton("▶️ يوتيوب", callback_data="cookies_youtube")
    btn_insta = types.InlineKeyboardButton("📸 انستغرام", callback_data="cookies_instagram")
    btn_facebook = types.InlineKeyboardButton("📘 فيسبوك", callback_data="cookies_facebook")
    btn_tiktok = types.InlineKeyboardButton("🎵 تيك توك", callback_data="cookies_tiktok")
    btn_check = types.InlineKeyboardButton("🔍 عرض الكل", callback_data="cookies_check_all")
    
    markup.add(btn_youtube, btn_insta)
    markup.add(btn_facebook, btn_tiktok)
    markup.add(btn_check)
    
    status_text = "🍪 **حالة الكوكيز:**\n\n"
    for platform, filename in COOKIE_FILES.items():
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            size = os.path.getsize(filename)
            status_text += f"✅ {platform.capitalize()}: {format_size(size)}\n"
        else:
            status_text += f"❌ {platform.capitalize()}: غير موجودة\n"
    
    msg = bot.send_message(user_id, status_text, reply_markup=markup)
    add_user_message(user_id, msg.message_id)

# ============================================
# 🗑️ أمر حذف الكوكيز
# ============================================
@bot.message_handler(commands=['deletecookies'])
def delete_cookies_menu(message):
    user_id = message.chat.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ هذا الأمر للمطور فقط")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_youtube = types.InlineKeyboardButton("🗑️ يوتيوب", callback_data="delete_youtube")
    btn_insta = types.InlineKeyboardButton("🗑️ انستغرام", callback_data="delete_instagram")
    btn_facebook = types.InlineKeyboardButton("🗑️ فيسبوك", callback_data="delete_facebook")
    btn_tiktok = types.InlineKeyboardButton("🗑️ تيك توك", callback_data="delete_tiktok")
    btn_all = types.InlineKeyboardButton("🗑️🗑️ حذف الكل", callback_data="delete_all")
    btn_cancel = types.InlineKeyboardButton("❌ إلغاء", callback_data="delete_cancel")
    
    markup.add(btn_youtube, btn_insta)
    markup.add(btn_facebook, btn_tiktok)
    markup.add(btn_all)
    markup.add(btn_cancel)
    
    msg = bot.send_message(
        user_id,
        "🗑️ **حذف الكوكيز**\n\nاختر المنصة التي تريد حذف كوكيزها:",
        reply_markup=markup
    )
    add_user_message(user_id, msg.message_id)

# ============================================
# 🔍 أمر التحقق من الكوكيز
# ============================================
@bot.message_handler(commands=['checkcookies'])
def check_all_cookies(message):
    user_id = message.chat.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ هذا الأمر للمطور فقط")
        return
    
    status_text = "🍪 **حالة الكوكيز:**\n\n"
    for platform, filename in COOKIE_FILES.items():
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            size = os.path.getsize(filename)
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = len(f.read().split('\n'))
                status_text += f"✅ **{platform.capitalize()}**\n"
                status_text += f"   📦 الحجم: {format_size(size)}\n"
                status_text += f"   📝 الأسطر: {lines}\n\n"
            except:
                status_text += f"✅ **{platform.capitalize()}**\n"
                status_text += f"   📦 الحجم: {format_size(size)}\n\n"
        else:
            status_text += f"❌ **{platform.capitalize()}**: غير موجودة\n\n"
    
    msg = bot.send_message(user_id, status_text)
    add_user_message(user_id, msg.message_id)

# ============================================
# ⏹️ معالجة زر إيقاف التحميل
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("stop_"))
def handle_stop_download(call):
    user_id = call.message.chat.id
    download_id = call.data.replace("stop_", "")
    
    try:
        bot.answer_callback_query(call.id, "⏹️ جاري إيقاف التحميل...")
    except:
        pass
    
    if stop_download(user_id, download_id):
        try:
            bot.edit_message_text(
                "⏹️ **تم إيقاف التحميل بنجاح!**\n\n"
                "🔄 يمكنك إرسال رابط جديد للتحميل",
                chat_id=user_id,
                message_id=call.message.message_id,
                parse_mode='Markdown'
            )
        except:
            pass
        
        try:
            for file in os.listdir('.'):
                if file.startswith(f'download_{user_id}_'):
                    os.remove(file)
                    print(f"🗑️ تم حذف الملف المؤقت: {file}")
        except:
            pass
    else:
        try:
            bot.edit_message_text(
                "❌ **لا يوجد تحميل نشط لإيقافه**",
                chat_id=user_id,
                message_id=call.message.message_id,
                parse_mode='Markdown'
            )
        except:
            pass

# ============================================
# 📨 معالجة اختيار المنصة
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("platform_"))
def handle_platform(call):
    user_id = call.message.chat.id
    platform = call.data.replace("platform_", "")
    
    if user_id in active_downloads and active_downloads[user_id]:
        bot.answer_callback_query(call.id, "⏳ يوجد تحميل نشط، انتظر حتى ينتهي", show_alert=True)
        return
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    delete_user_messages(user_id)
    
    msg = bot.send_message(user_id, f"📥 أرسل رابط {PLATFORM_NAMES.get(platform, platform)} الآن:")
    add_user_message(user_id, msg.message_id)
    
    user_states[user_id] = f"waiting_link_{platform}"

# ============================================
# 📝 معالجة الرسائل النصية
# ============================================
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_messages(message):
    user_id = message.chat.id
    text = message.text
    
    if text.startswith('/'):
        return
    
    if user_states.get(user_id) == "waiting_for_broadcast":
        if user_id != ADMIN_ID:
            user_states[user_id] = None
            return
        user_states[user_id] = None
        count = 0
        for u_id in users_db:
            try:
                bot.send_message(u_id, text)
                count += 1
                time.sleep(0.1)
            except:
                pass
        msg = bot.send_message(ADMIN_ID, f"✅ تم الإرسال إلى {count} مستخدم")
        add_user_message(ADMIN_ID, msg.message_id)
        return
    
    for platform in ['youtube', 'instagram', 'facebook', 'tiktok']:
        state = f"waiting_cookies_{platform}"
        if user_states.get(user_id) == state:
            if user_id != ADMIN_ID:
                user_states[user_id] = None
                return
            user_states[user_id] = None
            
            if save_cookies_from_text(platform, text):
                msg = bot.send_message(user_id, f"✅ تم حفظ كوكيز {platform.capitalize()} بنجاح!")
                add_user_message(user_id, msg.message_id)
                msg = bot.send_message(user_id, f"📢 الآن يمكنك تحميل المحتوى من {platform.capitalize()}!")
                add_user_message(user_id, msg.message_id)
            else:
                msg = bot.send_message(user_id, "❌ حدث خطأ في حفظ الكوكيز")
                add_user_message(user_id, msg.message_id)
            return
    
    if user_id in active_downloads and active_downloads[user_id]:
        msg = bot.send_message(user_id, "⏳ يوجد تحميل نشط، انتظر حتى ينتهي")
        add_user_message(user_id, msg.message_id)
        return
    
    for platform in ['youtube', 'instagram', 'facebook', 'tiktok']:
        state = f"waiting_link_{platform}"
        if user_states.get(user_id) == state:
            user_states[user_id] = None
            url_match = re.search(r'https?://[^\s]+', text)
            if url_match:
                url = url_match.group()
                short_id = generate_short_id(url)
                temp_links[short_id] = url
                
                try:
                    bot.delete_message(user_id, message.message_id)
                except:
                    pass
                
                delete_user_messages(user_id)
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                btn_video = types.InlineKeyboardButton("🎬 فيديو", callback_data=f"vid_{short_id}")
                btn_audio = types.InlineKeyboardButton("🎵 صوت", callback_data=f"aud_{short_id}")
                markup.add(btn_video, btn_audio)
                
                msg = bot.send_message(user_id, "🎯 اختر نوع التحميل:", reply_markup=markup)
                add_user_message(user_id, msg.message_id)
            else:
                msg = bot.send_message(user_id, "⚠️ أرسل رابطاً صحيحاً")
                add_user_message(user_id, msg.message_id)
            return
    
    url_match = re.search(r'https?://[^\s]+', text)
    if url_match:
        if user_id in active_downloads and active_downloads[user_id]:
            msg = bot.send_message(user_id, "⏳ يوجد تحميل نشط، انتظر حتى ينتهي")
            add_user_message(user_id, msg.message_id)
            return
            
        url = url_match.group()
        short_id = generate_short_id(url)
        temp_links[short_id] = url
        
        try:
            bot.delete_message(user_id, message.message_id)
        except:
            pass
        
        delete_user_messages(user_id)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_video = types.InlineKeyboardButton("🎬 فيديو", callback_data=f"vid_{short_id}")
        btn_audio = types.InlineKeyboardButton("🎵 صوت", callback_data=f"aud_{short_id}")
        markup.add(btn_video, btn_audio)
        
        msg = bot.send_message(user_id, "🎯 اختر نوع التحميل:", reply_markup=markup)
        add_user_message(user_id, msg.message_id)
    else:
        msg = bot.send_message(user_id, "⚠️ أرسل رابطاً صحيحاً")
        add_user_message(user_id, msg.message_id)

# ============================================
# 🎬 معالجة اختيار فيديو/صوت
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("vid_") or call.data.startswith("aud_"))
def handle_download(call):
    user_id = call.message.chat.id
    data = call.data
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    
    if user_id in active_downloads and active_downloads[user_id]:
        bot.answer_callback_query(call.id, "⏳ يوجد تحميل نشط، انتظر حتى ينتهي", show_alert=True)
        return
    
    is_video = data.startswith("vid_")
    short_id = data.replace("vid_", "") if is_video else data.replace("aud_", "")
    
    url = temp_links.get(short_id)
    if not url:
        msg = bot.send_message(user_id, "❌ انتهت صلاحية الرابط، أرسله مرة أخرى")
        add_user_message(user_id, msg.message_id)
        return
    
    if short_id in temp_links:
        del temp_links[short_id]
    
    media_type = "فيديو" if is_video else "صوت"
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    delete_user_messages(user_id)
    
    download_id = f"{user_id}_{int(time.time())}"
    active_downloads[user_id] = download_id
    download_processes[user_id] = download_id
    
    msg = bot.send_message(user_id, f"⏳ جاري تحميل {media_type}...")
    add_user_message(user_id, msg.message_id)
    timer_message_id = msg.message_id
    
    try:
        filename = download_with_progress(user_id, msg.message_id, url, is_video, media_type, download_id)
        
        if user_id in active_downloads and active_downloads[user_id] == download_id:
            del active_downloads[user_id]
        if user_id in download_processes and download_processes[user_id] == download_id:
            del download_processes[user_id]
        
        if filename and os.path.exists(filename):
            try:
                for _ in range(3):
                    animation = random.choice(DELETE_ANIMATIONS)
                    try:
                        bot.edit_message_text(
                            f"{animation} اكتمل التحميل!",
                            chat_id=user_id,
                            message_id=timer_message_id
                        )
                    except:
                        pass
                    time.sleep(0.2)
                bot.delete_message(user_id, timer_message_id)
            except:
                pass
            
            if user_id in user_messages and timer_message_id in user_messages[user_id]:
                user_messages[user_id].remove(timer_message_id)
            
            send_file(user_id, filename, is_video)
            
            try:
                os.remove(filename)
            except:
                pass
            
            delete_user_messages(user_id)
            
        else:
            msg = bot.send_message(user_id, "❌ لم يتم العثور على الملف")
            add_user_message(user_id, msg.message_id)
            
    except Exception as e:
        if user_id in active_downloads and active_downloads[user_id] == download_id:
            del active_downloads[user_id]
        if user_id in download_processes and download_processes[user_id] == download_id:
            del download_processes[user_id]
            
        error_msg = str(e)
        
        if "تم إيقاف التحميل" in error_msg:
            try:
                bot.edit_message_text(
                    "⏹️ **تم إيقاف التحميل بنجاح!**\n\n"
                    "🔄 يمكنك إرسال رابط جديد للتحميل",
                    chat_id=user_id,
                    message_id=msg.message_id,
                    parse_mode='Markdown'
                )
            except:
                pass
            return
            
        platform = get_platform_from_url(url)
        
        if "cookies" in error_msg.lower() or "authentication" in error_msg.lower() or "unreachable" in error_msg.lower():
            error_msg = (
                f"❌ **هذا المحتوى خاص أو يتطلب مصادقة**\n\n"
                f"💡 {PLATFORM_NAMES.get(platform, 'المنصة')} تحتاج كوكيز\n"
                f"📌 استخدم الأمر /cookies لإضافتها"
            )
        elif "not found" in error_msg.lower():
            error_msg = "❌ الرابط غير صحيح أو تم حذف المحتوى"
        else:
            error_msg = f"❌ حدث خطأ: {error_msg[:150]}"
        
        try:
            bot.edit_message_text(error_msg, user_id, msg.message_id, parse_mode='Markdown')
        except:
            msg = bot.send_message(user_id, error_msg)
            add_user_message(user_id, msg.message_id)

# ============================================
# 📁 معالجة استقبال الملفات (للكوكيز والإذاعة)
# ============================================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.chat.id
    
    is_cookie_waiting = False
    platform = None
    for p in ['youtube', 'instagram', 'facebook', 'tiktok']:
        if user_states.get(user_id) == f"waiting_cookies_{p}":
            is_cookie_waiting = True
            platform = p
            break
    
    if is_cookie_waiting and user_id == ADMIN_ID:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            file_content = downloaded_file.decode('utf-8', errors='ignore')
            
            if save_cookies_from_file(platform, file_content):
                msg = bot.send_message(user_id, f"✅ تم حفظ كوكيز {platform.capitalize()} بنجاح من الملف!")
                add_user_message(user_id, msg.message_id)
                msg = bot.send_message(user_id, f"📢 الآن يمكنك تحميل المحتوى من {platform.capitalize()}!")
                add_user_message(user_id, msg.message_id)
                user_states[user_id] = None
            else:
                msg = bot.send_message(user_id, "❌ لم يتم العثور على كوكيز صالحة في الملف. تأكد من أن الملف يحتوي على كوكيز انستغرام")
                add_user_message(user_id, msg.message_id)
                
        except Exception as e:
            msg = bot.send_message(user_id, f"❌ خطأ في قراءة الملف: {str(e)}")
            add_user_message(user_id, msg.message_id)
        return
    
    if user_states.get(user_id) == "waiting_for_broadcast" and user_id == ADMIN_ID:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            count = 0
            for u_id in users_db:
                try:
                    bot.send_document(u_id, downloaded_file, caption=message.caption)
                    count += 1
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Failed to send to {u_id}: {e}")
            
            user_states[user_id] = None
            bot.send_message(ADMIN_ID, f"✅ تم إرسال الملف إلى {count} مستخدم")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ خطأ في الإرسال: {str(e)}")
        return
    
    bot.reply_to(message, "⚠️ استخدم /admin ثم اختر إذاعة لإرسال الملفات، أو استخدم /cookies لإضافة كوكيز")

# ============================================
# 📸 معالجة الصور والفيديو والصوت للإذاعة
# ============================================
@bot.message_handler(content_types=['photo', 'video', 'audio', 'voice', 'animation'])
def handle_broadcast_media(message):
    user_id = message.chat.id
    
    if user_states.get(user_id) != "waiting_for_broadcast" or user_id != ADMIN_ID:
        bot.reply_to(message, "⚠️ استخدم /admin ثم اختر إذاعة لإرسال الملفات")
        return
    
    count = 0
    for u_id in users_db:
        try:
            if message.photo:
                bot.send_photo(u_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                bot.send_video(u_id, message.video.file_id, caption=message.caption)
            elif message.audio:
                bot.send_audio(u_id, message.audio.file_id, caption=message.caption)
            elif message.voice:
                bot.send_voice(u_id, message.voice.file_id)
            elif message.animation:
                bot.send_animation(u_id, message.animation.file_id, caption=message.caption)
            count += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"Failed to send to {u_id}: {e}")
    
    user_states[user_id] = None
    bot.send_message(ADMIN_ID, f"✅ تم إرسال الملف إلى {count} مستخدم")

# ============================================
# 🔘 معالجة أزرار لوحة الأدمن
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") or call.data.startswith("cookies_") or call.data.startswith("delete_") or call.data.startswith("replace_") or call.data.startswith("keep_"))
def handle_admin_buttons(call):
    user_id = call.message.chat.id
    data = call.data
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ هذا الأمر للمطور فقط", show_alert=True)
        return
    
    if data.startswith("delete_"):
        if data == "delete_all":
            count = delete_all_cookies()
            msg = bot.send_message(user_id, f"🗑️ تم حذف {count} ملفات كوكيز بنجاح!")
            add_user_message(user_id, msg.message_id)
            try:
                bot.delete_message(user_id, call.message.message_id)
            except:
                pass
            return
        
        if data == "delete_cancel":
            msg = bot.send_message(user_id, "❌ تم إلغاء الحذف")
            add_user_message(user_id, msg.message_id)
            try:
                bot.delete_message(user_id, call.message.message_id)
            except:
                pass
            return
        
        platform = data.replace("delete_", "")
        
        if delete_cookies(platform):
            msg = bot.send_message(user_id, f"🗑️ تم حذف كوكيز {platform.capitalize()} بنجاح!")
            add_user_message(user_id, msg.message_id)
        else:
            msg = bot.send_message(user_id, f"ℹ️ لا توجد كوكيز لـ {platform.capitalize()} لحذفها")
            add_user_message(user_id, msg.message_id)
        
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        return
    
    if data.startswith("cookies_"):
        platform = data.replace("cookies_", "")
        
        if platform == "check_all":
            status_text = "🍪 **حالة الكوكيز:**\n\n"
            for p, filename in COOKIE_FILES.items():
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    size = os.path.getsize(filename)
                    status_text += f"✅ {p.capitalize()}: {format_size(size)}\n"
                else:
                    status_text += f"❌ {p.capitalize()}: غير موجودة\n"
            msg = bot.send_message(user_id, status_text)
            add_user_message(user_id, msg.message_id)
            return
        
        if has_cookies(platform):
            filename = COOKIE_FILES[platform]
            size = os.path.getsize(filename)
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_replace = types.InlineKeyboardButton("🔄 استبدال", callback_data=f"replace_{platform}")
            btn_keep = types.InlineKeyboardButton("✅ الاحتفاظ", callback_data=f"keep_{platform}")
            btn_delete = types.InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_{platform}")
            markup.add(btn_replace, btn_keep, btn_delete)
            
            msg = bot.send_message(
                user_id,
                f"🍪 **كوكيز {platform.capitalize()}**\n\n"
                f"📦 الحجم: {format_size(size)}\n\n"
                "ماذا تريد أن تفعل؟",
                reply_markup=markup
            )
            add_user_message(user_id, msg.message_id)
            return
        
        msg = bot.send_message(
            user_id,
            f"📝 أرسل ملف الكوكيز لـ {platform.capitalize()}:\n\n"
            "📎 أرسل الملف كـ **Document** (ملف)\n"
            "أو الصق النص كرسالة"
        )
        add_user_message(user_id, msg.message_id)
        user_states[user_id] = f"waiting_cookies_{platform}"
        return
    
    if data.startswith("replace_"):
        platform = data.replace("replace_", "")
        msg = bot.send_message(
            user_id,
            f"📝 أرسل ملف الكوكيز الجديد لـ {platform.capitalize()}:"
        )
        add_user_message(user_id, msg.message_id)
        user_states[user_id] = f"waiting_cookies_{platform}"
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        return
    
    if data.startswith("keep_"):
        msg = bot.send_message(user_id, "✅ تم الاحتفاظ بالكوكيز الحالية")
        add_user_message(user_id, msg.message_id)
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        return
    
    if data == "admin_stats":
        msg = bot.send_message(ADMIN_ID, f"📊 **الإحصائيات:**\n\n✅ المشتركين: {len(users_db)} مستخدم")
        add_user_message(ADMIN_ID, msg.message_id)
        return
    
    elif data == "admin_broadcast":
        msg = bot.send_message(ADMIN_ID, "✍️ **أرسل المحتوى للإذاعة:**\n\n"
                               "📝 نص\n"
                               "🖼️ صورة\n"
                               "🎬 فيديو\n"
                               "🎵 صوت\n"
                               "📁 ملف\n\n"
                               "⚠️ سيرسل لكل المستخدمين")
        add_user_message(ADMIN_ID, msg.message_id)
        user_states[ADMIN_ID] = "waiting_for_broadcast"
        return
    
    elif data == "admin_cookies":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_youtube = types.InlineKeyboardButton("▶️ يوتيوب", callback_data="cookies_youtube")
        btn_insta = types.InlineKeyboardButton("📸 انستغرام", callback_data="cookies_instagram")
        btn_facebook = types.InlineKeyboardButton("📘 فيسبوك", callback_data="cookies_facebook")
        btn_tiktok = types.InlineKeyboardButton("🎵 تيك توك", callback_data="cookies_tiktok")
        btn_check = types.InlineKeyboardButton("🔍 عرض الكل", callback_data="cookies_check_all")
        
        markup.add(btn_youtube, btn_insta)
        markup.add(btn_facebook, btn_tiktok)
        markup.add(btn_check)
        
        status_text = "🍪 **إدارة الكوكيز:**\n\n"
        for platform, filename in COOKIE_FILES.items():
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                size = os.path.getsize(filename)
                status_text += f"✅ {platform.capitalize()}: {format_size(size)}\n"
            else:
                status_text += f"❌ {platform.capitalize()}: غير موجودة\n"
        
        msg = bot.send_message(ADMIN_ID, status_text, reply_markup=markup)
        add_user_message(ADMIN_ID, msg.message_id)
        return
    
    elif data == "admin_delete":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_youtube = types.InlineKeyboardButton("🗑️ يوتيوب", callback_data="delete_youtube")
        btn_insta = types.InlineKeyboardButton("🗑️ انستغرام", callback_data="delete_instagram")
        btn_facebook = types.InlineKeyboardButton("🗑️ فيسبوك", callback_data="delete_facebook")
        btn_tiktok = types.InlineKeyboardButton("🗑️ تيك توك", callback_data="delete_tiktok")
        btn_all = types.InlineKeyboardButton("🗑️🗑️ حذف الكل", callback_data="delete_all")
        btn_cancel = types.InlineKeyboardButton("❌ إلغاء", callback_data="delete_cancel")
        
        markup.add(btn_youtube, btn_insta)
        markup.add(btn_facebook, btn_tiktok)
        markup.add(btn_all)
        markup.add(btn_cancel)
        
        msg = bot.send_message(
            ADMIN_ID,
            "🗑️ **حذف الكوكيز**\n\nاختر المنصة التي تريد حذف كوكيزها:",
            reply_markup=markup
        )
        add_user_message(ADMIN_ID, msg.message_id)
        return
    
    elif data == "admin_info":
        info_text = (
            "🧑‍💻 **معلومات البوت:**\n\n"
            "🤖 وظيفة: تحميل الفيديو والصوت\n"
            "⚡ يدعم: يوتيوب، فيسبوك، انستغرام، تيك توك\n"
            "📦 يدعم الملفات الكبيرة\n"
            "⏱️ عداد تحميل متقدم وسلس\n"
            "📊 شريط تقدم دقيق ومتجدد\n"
            "🕌 آيات قرآنية أثناء التحميل\n"
            "⏹️ زر إيقاف التحميل\n"
            "📢 إذاعة متقدمة (نص، صورة، فيديو، صوت، ملف)\n"
            "🍪 يمكن إرسال الكوكيز كملف\n"
            "🗑️ يمكن حذف الكوكيز من البوت\n"
            "🧹 تنظيف تلقائي للرسائل\n"
            "🕐 توقيت سوريا (Asia/Damascus)\n"
            "🛠️ المطور: أحمد"
        )
        msg = bot.send_message(ADMIN_ID, info_text)
        add_user_message(ADMIN_ID, msg.message_id)
        return
    
    elif data == "admin_restart":
        msg = bot.send_message(ADMIN_ID, "🔄 جاري إعادة تشغيل البوت...")
        add_user_message(ADMIN_ID, msg.message_id)
        time.sleep(2)
        
        try:
            os.execv(sys.executable, ['python'] + sys.argv)
        except:
            bot.send_message(ADMIN_ID, "⚠️ يرجى إعادة تشغيل البوت يدوياً (اضغط Run)")
            os._exit(0)

# ============================================
# 🧹 تنظيف الروابط القديمة والرسائل
# ============================================
def cleanup_temp_links():
    while True:
        time.sleep(3600)
        try:
            temp_links.clear()
            for user_id in list(user_messages.keys()):
                if len(user_messages[user_id]) > 30:
                    user_messages[user_id] = user_messages[user_id][-30:]
        except:
            pass

cleanup_thread = threading.Thread(target=cleanup_temp_links, daemon=True)
cleanup_thread.start()

# ============================================
# 🚀 تشغيل البوت
# ============================================
if __name__ == "__main__":
    print("🤖 Bot is starting...")
    print("✅ Bot is ready!")
    
    try:
        syria_tz = pytz.timezone('Asia/Damascus')
        current_time = datetime.now(syria_tz).strftime("%I:%M %p")
        bot.send_message(ADMIN_ID, f"✅ **تم إعادة تشغيل البوت بنجاح!**\n\n🕐 الوقت: {current_time} (بتوقيت سوريا)")
    except:
        bot.send_message(ADMIN_ID, "✅ **تم إعادة تشغيل البوت بنجاح!**")
    
    print("📥 Just send any link to download")
    print("🧹 Messages are auto-cleaned with animation!")
    print("⏱️ Smooth and fast download timer!")
    print("📊 Live progress bar updates!")
    print("🕌 Quran verses appear during download!")
    print("⏹️ Stop download button added!")
    print("📢 Advanced broadcast (text, photo, video, audio, file)!")
    print("🔒 Active download protection enabled!")
    print("🕐 Timezone: Asia/Damascus (UTC+3)")
    
    print("\n🍪 Cookie Status:")
    for platform, filename in COOKIE_FILES.items():
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            print(f"   ✅ {platform.capitalize()}: {format_size(os.path.getsize(filename))}")
        else:
            print(f"   ❌ {platform.capitalize()}: Not found")
    
    while True:
        try:
            bot.infinity_polling(timeout=120, long_polling_timeout=120)
        except Exception as e:
            print(f"❌ Bot error: {e}")
            print("🔄 Restarting in 10 seconds...")
            time.sleep(10)
