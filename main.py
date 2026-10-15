import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("✨ Create Edit", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 Welcome to Wizzyfx\n\n1️⃣ Send video as FILE\n2️⃣ Send audio as FILE\n3️⃣ Tap Create Edit", reply_markup=menu())

# --- MESSAGE FLOW YOU WANTED ---
async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    has_both = "video" in context.user_data and "audio" in context.user_data
    if has_both:
        await update.message.reply_text("✅ Got both! Ready to edit.", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Video received.\n\n👉 Now send your audio as FILE", reply_markup=menu(False))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    has_both = "video" in context.user_data and "audio" in context.user_data
    if has_both:
        await update.message.reply_text("✅ Got both! Ready to edit.", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Audio received.\n\n👉 Now send your video as FILE", reply_markup=menu(False))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("Please send video and audio first."); return
    status=await update_msg.reply_text("⏳ Creating your edit... 20 sec")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"]); af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🎬 Editing - fast mode, no black...")
            def process():
                vclip=VideoFileClip(v_in); aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                cut_len=0.45
                clips=[]; total=0
                src_dur=vclip.duration
                while total < song_dur:
                    max_start=max(0, src_dur-cut_len-0.01)
                    s=random.uniform(0, max_start) if src_dur>cut_len else 0
                    seg=vclip.subclip(s, min(s+cut_len, src_dur))
                    clips.append(seg)
                    total+=seg.duration
                    if len(clips)>100: break
                final_main=concatenate_videoclips(clips, method="compose").subclip(0, song_dur)
                # Tiny watermark - SUPER LIGHT (TextClip is faster than PIL)
                try:
                    txt=TextClip("Wizzyfx", fontsize=18, color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.6)
                    final=CompositeVideoClip([final_main, txt], size=vclip.size).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✨ Made with Wizzyfx")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-1500:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="help": await q.message.reply_text("How it works:\n1. Video as FILE\n2. Audio as FILE\n3. Tap Create Edit")
    else: await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
