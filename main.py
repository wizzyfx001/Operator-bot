import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("✨ Create Edit - KAM Style", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 Wizzyfx - KAM_CUTS STYLE 🔥\n\n1️⃣ Video as FILE\n2️⃣ Audio as FILE\n3️⃣ Tap Create Edit\n\nStyle: Cue The Music, punch zooms, beat sync", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    if "audio" in context.user_data:
        await update.message.reply_text("✅ Got both! Ready for KAM edit.", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Video received.\n👉 Now send audio as FILE", reply_markup=menu(False))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    if "video" in context.user_data:
        await update.message.reply_text("✅ Got both! Ready for KAM edit.", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Audio received.\n👉 Now send video as FILE", reply_markup=menu(False))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("Send both first."); return
    status=await update_msg.reply_text("⏳ Creating KAM_CUTS edit... 30 sec")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"]); af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🎬 KAM Style: cue, zoom punch, beat sync...")
            def process():
                vclip=VideoFileClip(v_in); aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclip.size
                clips=[]
                # KAM intro: first 1.5 sec - first clip with text CUE THE MUSIC
                src_dur=vclip.duration
                def rand_seg(dur):
                    max_s=max(0, src_dur-dur-0.01)
                    s=random.uniform(0, max_s) if max_s>0 else 0
                    return vclip.subclip(s, min(s+dur, src_dur))
                
                # 0-2 sec - CUE THE MUSIC style
                seg0=rand_seg(1.8)
                # punch zoom effect
                seg0=seg0.resize(1.25).crop(x_center=seg0.w/2, y_center=seg0.h/2, width=W, height=H)
                try:
                    txt1=TextClip("CUE THE\nMUSIC", fontsize=int(H*0.09), color='white', stroke_color='red', stroke_width=2, font='DejaVu-Sans-Bold', method='caption', size=(W*0.6, None)).set_duration(0.9).set_position((0.55,0.45)).set_opacity(0.9)
                    seg0_comp=CompositeVideoClip([seg0, txt1], size=(W,H)).set_duration(seg0.duration)
                    clips.append(seg0_comp)
                except:
                    clips.append(seg0)
                
                # 2-3.5 sec YOU READY?
                seg1=rand_seg(1.2)
                seg1=seg1.fx(vfx.speedx, 1.3)
                try:
                    txt2=TextClip("YOU\nREADY?", fontsize=int(H*0.1), color='white', stroke_color='red', stroke_width=2, font='DejaVu-Sans-Bold', method='caption', size=(W*0.5, None)).set_duration(0.8).set_position((0.55,0.5)).set_opacity(0.9)
                    seg1_comp=CompositeVideoClip([seg1, txt2], size=(W,H)).set_duration(seg1.duration)
                    clips.append(seg1_comp)
                except:
                    clips.append(seg1)

                # Main beat - fast punch zooms like your video (0.3-0.5 sec cuts)
                total=3.0
                idx=0
                while total < song_dur:
                    cut=random.choice([0.28, 0.32, 0.4, 0.5]) # KAM timing
                    if total+cut > song_dur:
                        cut=song_dur-total
                    seg=rand_seg(cut)
                    # KAM effects: zoom punch + speed
                    if idx % 2 == 0:
                        # punch in
                        seg=seg.resize(1.35).crop(x_center=seg.w/2 + random.randint(-20,20), y_center=seg.h/2 + random.randint(-15,15), width=W, height=H).fx(vfx.speedx, random.uniform(1.6,2.2))
                    else:
                        seg=seg.fx(vfx.speedx, random.uniform(1.2,1.8))
                        if random.random()<0.4:
                            seg=seg.fx(vfx.mirror_x)
                    # white flash on heavy beat
                    if idx % 6 == 0:
                        clips.append(ColorClip(size=(W,H), color=(255,255,255), duration=0.04))
                        total+=0.04
                    clips.append(seg)
                    total+=cut
                    idx+=1
                    if idx>80: break
                
                final_main=concatenate_videoclips(clips, method="compose").subclip(0, song_dur)
                # tiny Wizzyfx watermark you liked
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.035), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.55)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading KAM edit...")
            await update_msg.reply_video(video=open(out,'rb'), caption="🔥 KAM_CUTS style - Made with Wizzyfx")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-2000:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="help": await q.message.reply_text("KAM style:\nVideo as FILE + Audio as FILE\nBot adds CUE THE MUSIC, punch zooms, beat sync like your example")
    else: await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
