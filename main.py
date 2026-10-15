import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Create Edit - V20 NO BLACK", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 Wizzyfx V20 - GUARANTEED NO BLACK\n\n1️⃣ Video as FILE\n2️⃣ Audio as FILE", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    await update.message.reply_text("✅ Got both! Ready" if "audio" in context.user_data else "✅ Video received.\n👉 Now send audio as FILE", reply_markup=menu("audio" in context.user_data))
async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    await update.message.reply_text("✅ Got both! Ready" if "video" in context.user_data else "✅ Audio received.\n👉 Now send video as FILE", reply_markup=menu("video" in context.user_data))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("Send both first."); return
    status=await update_msg.reply_text("⏳ V20 Creating - NO BLACK guarantee...")
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
                def rand_seg(dur):
                    max_s=max(0, src_dur-dur-0.01)
                    s=random.uniform(0, max_s) if max_s>0 else 0
                    return vclip.subclip(s, s+dur)
                
                # BUILD until MORE than song_dur
                clips=[]; total=0
                attempts=0
                while total < song_dur + 1: # build 1 sec extra to be safe
                    cut=random.uniform(0.28,0.45)
                    seg=rand_seg(cut)
                    if random.random()<0.6:
                        seg=seg.resize(1.35).crop(x_center=W/2+random.randint(-20,20), y_center=H/2, width=W, height=H).fx(vfx.speedx, random.uniform(1.5,2.2))
                    clips.append(seg)
                    total+=cut
                    attempts+=1
                    if attempts>150: break
                
                # Concatenate and FORCE cut to exactly song_dur - NO BLACK
                base=concatenate_videoclips(clips, method="compose")
                # If base is shorter (rare), loop it
                if base.duration < song_dur:
                    base=base.loop(duration=song_dur)
                final_main=base.subclip(0, song_dur) # cut to exact - no black
                
                # Tiny Wizzyfx
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.032), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.5)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close(); base.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading - no black...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V20 - No black 100% - Wizzyfx")
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
