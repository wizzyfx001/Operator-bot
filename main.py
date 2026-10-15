import os, tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from moviepy.editor import VideoFileClip, AudioFileClip

BOT_TOKEN = os.getenv("BOT_TOKEN")
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Bot Ready!\n1. Send me video\n2. Send me phonk mp3\nI will edit sharp and send back.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    file = await update.message.video.get_file() if update.message.video else await update.message.document.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tf:
        await file.download_to_drive(tf.name)
        user_data[uid] = {"video": tf.name}
    await update.message.reply_text("✅ Video saved! Now send phonk music.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_data:
        await update.message.reply_text("Send video first")
        return
    await update.message.reply_text("⏳ Editing... wait 60 sec")
    file = await update.message.audio.get_file() if update.message.audio else await update.message.document.get_file() if update.message.document else await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
        await file.download_to_drive(tf.name)
        audio_path = tf.name
    video_path = user_data[uid]["video"]
    out = tempfile.mktemp(suffix=".mp4")
    try:
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)
        if audio.duration > video.duration:
            audio = audio.subclip(0, video.duration)
        else:
            video = video.subclip(0, audio.duration)
        video = video.resize(height=1080)
        final = video.set_audio(audio)
        final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None)
        await update.message.reply_video(video=open(out, 'rb'), caption="✅ Done! Send new video to edit again.")
        video.close(); audio.close(); final.close()
        os.remove(out); os.remove(audio_path)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.Document.AUDIO | filters.VOICE, handle_audio))
    app.run_polling()

if __name__ == "__main__":
    main()
