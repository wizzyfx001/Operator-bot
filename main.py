import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Create KAM Edit", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 Wizzyfx - KAM_CUTS Style\n\n1️⃣ Send VIDEO as FILE\n2️⃣ Send AUDIO as FILE\n3️⃣ Tap Create Edit", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    if "audio" in context.user_data:
        await update.message.reply_text("✅ Got both! Ready.", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Video received.\n👉 Now send your audio as FILE", reply_markup=menu(False))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    if "video" in context.user_data:
        await update.message.reply_text("✅ Got both! Ready.", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Audio received.\n👉 Now send your video as FILE", reply_markup=menu(False))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("Send both files first."); return
    status=await update_msg.reply_text("⏳ Creating KAM edit - 25 sec...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"]); af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🎬 Cutting - no black, KAM punch...")
            def process():
                vclip=VideoFileClip(v_in); aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclip.size
                src_dur=vclip.duration
                def rand_seg(dur):
                    max_s=max(0, src_dur-dur-0.02)
                    s=random.uniform(0, max_s) if max_s>0 else 0
                    return vclip.subclip(s, min(s+dur, src_dur))
                clips=[]
                # KAM intro - CUE THE MUSIC (first 2 sec)
                seg0=rand_seg(2.0).resize(1.25).crop(x_center=W/2, y_center=H/2, width=W, height=H)
                try:
                    txt=TextClip("CUE THE\nMUSIC", fontsize=int(H*0.085), color='white', stroke_color='red', stroke_width=2, font='DejaVu-Sans-Bold', method='caption', size=(W*0.55, None)).set_duration(1.0).set_position((0.55,0.45))
                    seg0=CompositeVideoClip([seg0, txt], size=(W,H)).set_duration(2.0)
                except: pass
                clips.append(seg0)
                total=2.0
                idx=0
                # Fill rest until song_dur - NO BLACK
                while total < song_dur - 0.05:
                    cut=random.choice([0.32, 0.38, 0.45])
                    if total+cut > song_dur: cut=song_dur-total
                    seg=rand_seg(cut)
                    # KAM punch zoom
                    if idx % 2 == 0:
                        seg=seg.resize(1.35).crop(x_center=W/2+random.randint(-25,25), y_center=H/2+random.randint(-15,15), width=W, height=H).fx(vfx.speedx, random.uniform(1.7,2.3))
                    else:
                        seg=seg.fx(vfx.speedx, random.uniform(1.3,1.8))
                    clips.append(seg)
                    total+=cut
                    idx+=1
                    if idx>100: break
                final_main=concatenate_videoclips(clips, method="compose")
                final_main=final_main.subclip(0, song_dur) # FORCE exact duration
                # Tiny watermark bottom left - light & fast
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.035), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.55)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="🔥 KAM_CUTS style - Wizzyfx")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-1500:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="help": await q.message.reply_text("How: Send video as FILE, audio as FILE, tap Create KAM Edit")
    else: await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
