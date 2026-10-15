import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 EDIT 20s + Wizzyfx", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(f"🔥 V11.1 Wizzyfx\n✅ {MAX_DURATION}s max\n✅ No white bug\n✅ Wizzyfx outro\n1. Video as FILE\n2. MP3 as FILE\n3. /edit", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    has_both="video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Video! {'Ready!' if has_both else 'Now MP3'}", reply_markup=menu(has_both))
async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    has_both="video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Music! {'Ready!' if has_both else 'Now video'}", reply_markup=menu(has_both))

async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("❌ Send both first!"); return
    status=await update_msg.reply_text("🥁 Downloading...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip, ImageClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"])
            af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text(f"🎧 Analyzing beats...")

            def process():
                vclip=VideoFileClip(v_in)
                aclip=AudioFileClip(a_in)
                beat_times=[]
                try:
                    import librosa
                    y,sr=librosa.load(a_in, duration=MAX_DURATION+5)
                    tempo,bf=librosa.beat.beat_track(y=y, sr=sr, units='time')
                    beat_times=[float(b) for b in bf if b < min(aclip.duration, MAX_DURATION)]
                except: pass
                if len(beat_times)<8:
                    interval=60.0/142
                    dur=min(aclip.duration, MAX_DURATION)
                    beat_times=[i*interval for i in range(int(dur/interval))]
                song_dur=min(aclip.duration, MAX_DURATION)
                main_dur=song_dur-1.5 if song_dur>6 else song_dur
                add_outro= song_dur>6
                beat_times=[b for b in beat_times if b<main_dur]
                if len(beat_times)<2: beat_times=[0,main_dur]
                clips=[]
                src_dur=vclip.duration
                for i in range(len(beat_times)-1):
                    b_end=beat_times[i+1]; b_start=beat_times[i]
                    cut_len=b_end-b_start
                    if cut_len>0.8: cut_len=0.6
                    if cut_len<0.15: cut_len=0.22
                    max_start=max(0,src_dur-cut_len-0.05)
                    if random.random()<0.7 and src_dur>2:
                        src_start=random.uniform(src_dur*0.25, max(src_dur*0.25, src_dur*0.75-cut_len))
                    else:
                        src_start=random.uniform(0,max_start)
                    seg=vclip.subclip(src_start, src_start+cut_len)
                    if i%8==0:
                        seg=seg.resize(1.4).crop(x_center=seg.w/2, y_center=seg.h/2, width=vclip.w, height=vclip.h).fx(vfx.speedx,0.75)
                    elif i%2==0:
                        seg=seg.fx(vfx.speedx, random.uniform(1.8,2.6))
                    else:
                        if random.random()<0.5: seg=seg.fx(vfx.time_mirror)
                        seg=seg.fx(vfx.speedx, random.uniform(1.3,2.0))
                    if random.random()<0.25: seg=seg.fx(vfx.mirror_x)
                    clips.append(seg)
                    if i%4==0 and i < len(beat_times)-4:
                        clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.04))
                final_main=concatenate_videoclips(clips, method="compose").subclip(0,main_dur)
                if add_outro:
                    from PIL import Image, ImageDraw, ImageFont
                    W,H=vclip.size
                    img=Image.new('RGB',(W,H),(0,0,0))
                    draw=ImageDraw.Draw(img)
                    try:
                        try:
                            font_big=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=int(H*0.18))
                        except:
                            font_big=ImageFont.load_default()
                        text="Wizzyfx"
                        bbox=draw.textbbox((0,0),text,font=font_big)
                        w,h=bbox[2]-bbox[0], bbox[3]-bbox[1]
                        # glow effect - draw purple outline
                        for dx in [-3,3]:
                            for dy in [-3,3]:
                                draw.text(((W-w)//2+dx, (H-h)//2+dy), text, font=font_big, fill=(120,40,255))
                        draw.text(((W-w)//2, (H-h)//2), text, font=font_big, fill=(255,255,255))
                    except Exception as e:
                        print(e)
                        draw.text((W//3,H//2),"Wizzyfx",fill=(255,255,255))
                    outro_path=os.path.join(tmp,"outro.png")
                    img.save(outro_path)
                    outro_clip=ImageClip(outro_path, duration=1.5)
                    final=concatenate_videoclips([final_main, outro_clip], method="compose")
                else:
                    final=final_main
                final=final.set_audio(aclip.subclip(0,final.duration))
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="🔥 V11.1 20s + Wizzyfx")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"❌ {e}\n{traceback.format_exc()[-4000:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
