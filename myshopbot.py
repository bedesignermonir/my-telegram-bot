import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- আপনার তথ্য ---
BOT_TOKEN = "5784807075:AAFk42jjcrjeZBsSHXEKUmhzbPCqzvvtNFU"
GROUP_ID = -1003582838237 

# ডাটাবেস
user_to_topic = {}  
topic_to_user = {}  
user_files = {} 

# পাসপোর্টের রেট
PASSPORT_RATES = {
    "48_5_Regular": 4525, "48_5_Express": 6825, "48_5_Super": 9125,
    "48_10_Regular": 6250, "48_10_Express": 8550, "48_10_Super": 10850,
    "64_5_Regular": 6825, "64_5_Express": 9125, "64_5_Super": 12575,
    "64_10_Regular": 8550, "64_10_Express": 10350, "64_10_Super": 14300
}

# --- Render Port Binding (Health Check) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")

def run_health_check():
    # Render অটোমেটিক একটি পোর্ট প্রোভাইড করে, সেটি ব্যবহার করা
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- কিবোর্ডস ---
def payment_methods_kb(amount):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"বিকাশ ({amount} TK)", callback_data=f"pay_bkash_{amount}")],
        [InlineKeyboardButton(f"নগদ ({amount} TK)", callback_data=f"pay_nagad_{amount}")]
    ])

def job_payment_options_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("নিজে পেমেন্ট করবো", callback_data="job_pay_self")],
        [InlineKeyboardButton("আপনাদের মাধ্যমে করবো", callback_data="job_pay_admin")]
    ])

# --- কমান্ড হ্যান্ডলার ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ABC Computer-এ স্বাগতম। সেবা বেছে নিন:\n/passport, /nid, /typing, /job")

async def job_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['service'] = "Job"
    await update.message.reply_text("চাকরির ডকুমেন্ট ও সার্কুলার পাঠান। শেষ হলে 'Done' ক্লিক করুন।", 
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ ফাইল পাঠানো শেষ", callback_data="user_files_done")]]))

async def passport_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['service'] = "Passport"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("৪৮ পাতা", callback_data="pp_48"), InlineKeyboardButton("৬৪ পাতা", callback_data="pp_64")]])
    await update.message.reply_text("পাসপোর্ট পাতা সিলেক্ট করুন:", reply_markup=kb)

# --- বাটন কলব্যাক ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    thread_id = user_to_topic.get(user_id)
    await query.answer()

    if data == "user_files_done":
        service = context.user_data.get('service')
        if service == "Job":
            await query.edit_message_text("আবেদন সার্ভিস চার্জ ১০০ টাকা। পেমেন্ট করুন:", reply_markup=payment_methods_kb(100))
    
    elif data == "job_pay_admin":
        await query.edit_message_text("অফিস থেকে পেমেন্টের অংক জানানো হচ্ছে, দয়া করে অপেক্ষা করুন...")
        await context.bot.send_message(chat_id=GROUP_ID, message_thread_id=thread_id, 
                                     text="⚠️ ইউজার 'আপনাদের মাধ্যমে' পেমেন্ট সিলেক্ট করেছে। দয়া করে শুধু টাকার পরিমাণটি লিখে পাঠান।")
    
    elif data == "job_pay_self":
        await query.edit_message_text("ঠিক আছে, আপনি নিজে পেমেন্ট সম্পন্ন করে কনফার করুন।")

# --- মেসেজ হ্যান্ডলিং ---
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if chat_id == GROUP_ID:
        target_user_id = topic_to_user.get(msg.message_thread_id)
        if target_user_id:
            text = msg.text.lower().strip() if msg.text else ""
            
            if text == 'ok':
                await context.bot.send_message(chat_id=target_user_id, text="পেমেন্ট সফলভাবে গ্রহণ করা হয়েছে! অনুগ্রহ করে মেসেজের জন্য অপেক্ষা করুন, আপনার কাজ চলছে...")
                if target_user_id in user_files:
                    for f_msg_id in user_files[target_user_id]:
                        await context.bot.forward_message(chat_id=GROUP_ID, from_chat_id=target_user_id, message_id=f_msg_id, message_thread_id=msg.message_thread_id)
                    del user_files[target_user_id]
                await msg.reply_text("✅ কাস্টমারকে পেমেন্ট কনফার্মেশন পাঠানো হয়েছে।")

            elif text == 'all done':
                await context.bot.send_message(chat_id=target_user_id, text="✅ অভিনন্দন! আপনার আবেদন বা কাজটি সফলভাবে সম্পন্ন হয়েছে।\n\nনতুন আবেদনের জন্য পুনরায় /start লিখুন।")
                if target_user_id in user_to_topic: del user_to_topic[target_user_id]
                await msg.reply_text("🏁 কাজ সম্পন্ন। সেশন ক্লোজ করা হয়েছে।")
                
            elif text.isdigit():
                amount = int(text)
                await context.bot.send_message(chat_id=target_user_id, text=f"আপনার সরকারি ফি {amount} টাকা পেমেন্ট করুন:", reply_markup=payment_methods_kb(amount))
            
            else:
                await context.bot.copy_message(chat_id=target_user_id, from_chat_id=GROUP_ID, message_id=msg.message_id)
                if msg.document and ".pdf" in msg.document.file_name.lower():
                    await context.bot.send_message(chat_id=target_user_id, text="আপনার আবেদন সম্পন্ন হয়েছে। সরকারি ফি পেমেন্ট কিভাবে করবেন?", reply_markup=job_payment_options_kb())
        return

    if user_id not in user_to_topic:
        topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{update.effective_user.first_name}")
        user_to_topic[user_id] = topic.message_thread_id
        topic_to_user[topic.message_thread_id] = user_id
    
    if user_id not in user_files: user_files[user_id] = []
    if not (msg.text and msg.text.startswith('/')):
        user_files[user_id].append(msg.message_id)

    if msg.text:
        await context.bot.copy_message(chat_id=GROUP_ID, from_chat_id=chat_id, message_id=msg.message_id, message_thread_id=user_to_topic[user_id])

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("job", job_cmd))
    app.add_handler(CommandHandler("passport", passport_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    
    # পোলিং শুরু
    app.run_polling()

if __name__ == '__main__':
    # আলাদা থ্রেডে হেলথ চেক সার্ভার চালু করা (Render-এর জন্য)
    threading.Thread(target=run_health_check, daemon=True).start()
    
    # বট মেইন ফাংশন চালু করা
    main()