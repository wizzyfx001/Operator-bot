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
    await update.message.reply_text("👋 Welcome to Wizzyfx\n\n🔥 Pro Phonk Edits\n\n1️⃣ Video as FILE\n2️⃣ Audio as FILE\n3️⃣ Tap Create Edit", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    await update.message.reply_text("✅ Ready!" if "audio" in context.user_data else "✅ Video received.", reply_markup=menu("audio" in context.user_data))
async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    await update.message.reply_text("✅ Ready!" if "video" in context.user_data else "✅ Audio received.", reply_markup=menu("video" in context.user_data))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("Send both first."); return
    status=await update_msg.reply_text("⏳ Creating edit...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip, ImageClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"]); af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🎬 Cutting - no black fix...")
            def process():
                vclip=VideoFileClip(v_in); aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                interval=60.0/142
                clips=[]; total=0; idx=0
                src_dur=vclip.duration
                # FIX: loop until we REALLY fill song_dur
                while total < song_dur:
                    cut_len=interval
                    if idx%6==0 and idx>0 and total+0.03 < song_dur:
                        clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.03))
                        total+=0.03
                    # pick random cool moment
                    max_start=max(0, src_dur-cut_len-0.05)
                    src_start=random.uniform(src_dur*0.1, max(src_dur*0.1, src_dur*0.9-cut_len)) if src_dur>1.5 else 0
                    seg=vclip.subclip(src_start, min(src_start+cut_len, src_dur))
                    # ensure seg has duration
                    if seg.duration < 0.1:
                        seg=vclip.subclip(0, cut_len)
                    if idx%8==0:
                        seg=seg.resize(1.3).crop(x_center=seg.w/2, y_center=seg.h/2, width=vclip.w, height=vclip.h).fx(vfx.speedx,0.85)
                    elif idx%2==0:
                        seg=seg.fx(vfx.speedx, random.uniform(1.8,2.4))
                    else:
                        if random.random()<0.4: seg=seg.fx(vfx.time_mirror)
                        seg=seg.fx(vfx.speedx, random.uniform(1.3,1.9))
                    if random.random()<0.25: seg=seg.fx(vfx.mirror_x)
                    clips.append(seg)
                    total+=seg.duration
                    idx+=1
                    if idx>200: break # safety
                final_main=concatenate_videoclips(clips, method="compose").subclip(0, song_dur)
                # Tiny watermark bottom left - KEEP AS YOU LIKED
                from PIL import Image, ImageDraw, ImageFont
                W,H=vclip.size
                wm_w, wm_h=int(W*0.28), int(H*0.08)
                wm_img=Image.new('RGBA',(wm_w, wm_h),(0,0,0,0))
                draw=ImageDraw.Draw(wm_img)
                try:
                    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=int(H*0.032))
                except:
                    font=ImageFont.load_default()
                draw.text((1,1), "Wizzyfx", font=font, fill=(100,40,200,160))
                draw.text((0,0), "Wizzyfx", font=font, fill=(255,255,255,110))
                wm_path=os.path.join(tmp,"wm.png"); wm_img.save(wm_path)
                watermark=ImageClip(wm_path, duration=song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.65)
                final=CompositeVideoClip([final_main, watermark], size=vclip.size).set_audio(aclip.subclip(0,song_dur))
                final=final.set_duration(song_dur) # FORCE duration = no black
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✨ Made with Wizzyfx")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="help": await q.message.reply_text("Send video as FILE + audio as FILE")
    else: await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
