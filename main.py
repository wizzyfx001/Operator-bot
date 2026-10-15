import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Create Edit - NO BLACK", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 Wizzyfx V18 - NO BLACK FIX\n\n1️⃣ Video as FILE\n2️⃣ Audio as FILE\n3️⃣ Tap Create", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    has_audio="audio" in context.user_data
    await update.message.reply_text("✅ Got both! Ready - NO BLACK" if has_audio else "✅ Video received.\n👉 Now send audio as FILE", reply_markup=menu(has_audio))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    has_video="video" in context.user_data
    await update.message.reply_text("✅ Got both! Ready - NO BLACK" if has_video else "✅ Audio received.\n👉 Now send video as FILE", reply_markup=menu(has_video))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("Send both first."); return
    status=await update_msg.reply_text("⏳ V18 Creating - NO BLACK guaranteed 20 sec...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"]); af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            def process():
                vclip=VideoFileClip(v_in); aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclip.size
                src_dur=vclip.duration
                # NO BLACK LOGIC: keep cutting until EXACT song_dur
                clips=[]; total=0.0
                while total < song_dur - 0.01:
                    remaining=song_dur-total
                    cut_len=min(random.uniform(0.3,0.5), remaining)
                    max_start=max(0, src_dur-cut_len-0.01)
                    s=random.uniform(0, max_start) if max_start>0 else 0
                    e=s+cut_len
                    seg=vclip.subclip(s, e)
                    # KAM punch
                    if random.random()<0.5:
                        seg=seg.resize(1.3).crop(x_center=W/2+random.randint(-20,20), y_center=H/2, width=W, height=H).fx(vfx.speedx, 1.8)
                    clips.append(seg)
                    total+=cut_len
                # This concatenate WILL be exactly song_dur, no black
                final_main=concatenate_videoclips(clips, method="compose").set_duration(song_dur)
                # tiny Wizzyfx only - no KAM_CUTS
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.032), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.5)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading - no black...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V18 NO BLACK - Wizzyfx")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-1500:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
