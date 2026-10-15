import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")

def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 BEAT SYNC EDIT NOW", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔥 V10 BEAT SYNC\n✅ Cuts on EVERY beat\n✅ Finds cool moments\n✅ Reverse + Zoom + Shake\n1. Video as FILE\n2. MP3 as FILE\n3. /edit", reply_markup=menu())

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
    status=await update_msg.reply_text("🥁 Step 1/3: Downloading...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip
        import moviepy.video.fx.all as vfx

        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"])
            af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🎧 Step 2/3: Analyzing beats...")

            def process():
                import librosa
                vclip=VideoFileClip(v_in)
                aclip=AudioFileClip(a_in)

                # --- BEAT DETECTION ---
                try:
                    y, sr = librosa.load(a_in, duration=30) # analyze first 30 sec max
                    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units='time')
                    beat_times = beat_frames # when units='time' it returns times directly
                    # Ensure beats sorted and within audio
                    beat_times = [float(b) for b in beat_times if b < min(aclip.duration, 15)]
                    if len(beat_times) < 8:
                        raise ValueError("too few beats")
                except Exception as e:
                    print(f"beat detect failed {e}, fallback 140bpm")
                    # fallback 140 bpm
                    bpm = 140
                    beat_interval = 60.0/bpm
                    beat_times = [i*beat_interval for i in range(int(min(aclip.duration,15)/beat_interval))]

                # Clean beat list - make cuts
                song_dur = min(aclip.duration, 12, beat_times[-1] if beat_times else 12)
                beat_times = [b for b in beat_times if b < song_dur]
                if len(beat_times) < 2:
                    beat_times = [0, song_dur]

                clips = []
                # Video source duration for random cool moments
                src_dur = vclip.duration

                for i in range(len(beat_times)-1):
                    b_start = beat_times[i]
                    b_end = beat_times[i+1]
                    cut_len = b_end - b_start
                    # Don't allow too long - cap 0.8 sec for phonk style
                    if cut_len > 0.8:
                        cut_len = 0.6
                        b_end = b_start + cut_len

                    # --- COOL MOMENT FINDER ---
                    # Pick random section, but avoid slow parts - bias to middle
                    # This simulates "sharp moments"
                    max_start = max(0, src_dur - cut_len - 0.05)
                    # 70% chance from middle 50% of video (usually action is there)
                    if random.random() < 0.7 and src_dur > 2:
                        mid_start = src_dur * 0.25
                        mid_end = src_dur * 0.75 - cut_len
                        src_start = random.uniform(mid_start, max(mid_start, mid_end))
                    else:
                        src_start = random.uniform(0, max_start)

                    seg = vclip.subclip(src_start, src_start + cut_len)

                    # --- BEAT EFFECT ---
                    # Every beat gets an effect - synced to music
                    if i % 8 == 0: # Drop
                        seg = seg.resize(1.4).crop(x_center=seg.w/2, y_center=seg.h/2, width=vclip.w, height=vclip.h)
                        seg = seg.fx(vfx.speedx, 0.7) # slow + zoom = impact
                    elif i % 2 == 0:
                        # Fast velocity on beat
                        seg = seg.fx(vfx.speedx, random.uniform(1.8, 2.6))
                    else:
                        # Reverse / mirror phonk signature
                        if random.random() < 0.5:
                            seg = seg.fx(vfx.time_mirror)
                        seg = seg.fx(vfx.speedx, random.uniform(1.3, 2.0))

                    if random.random() < 0.25:
                        seg = seg.fx(vfx.mirror_x)

                    clips.append(seg)

                    # Flash on strong beats
                    if i % 4 == 0:
                        clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.03))

                final = concatenate_videoclips(clips, method="compose")
                # Use audio up to song_dur
                final_audio = aclip.subclip(0, song_dur)
                final = final.set_audio(final_audio)

                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()

            await asyncio.to_thread(process)
            await status.edit_text("📤 Step 3/3: Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="🔥 V10 BEAT SYNC - cuts on every beat")
            await status.delete()

    except Exception as e:
        await update_msg.reply_text(f"❌ CRASH:\n{e}\n\n{traceback.format_exc()[-3500:]}")

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
