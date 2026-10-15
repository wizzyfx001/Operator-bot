import os, tempfile, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

def menu(has_both=False):
    if has_both:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 EDIT TO MY BEAT NOW", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("📋 How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🔥 OPERATOR V7 - BEAT SYNC\n\n"
        "How to use:\n"
        "1. Send video clip (5-15s)\n"
        "2. Send punk music MP3\n"
        "3. I auto-edit to the beats\n\n"
        "Fixed for Redmi MTK - Baseline 3.0",
        reply_markup=menu()
    )

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fid = (update.message.video or update.message.document).file_id
    context.user_data["video"] = fid
    has_both = "video" in context.user_data and "audio" in context.user_data
    
    if has_both:
        await update.message.reply_text("✅ Video saved! + Music already saved! Ready?", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Video saved! Now send the punk music MP3 (as audio file)")

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Accept mp3, m4a, ogg, audio, voice, document audio
    fid = (update.message.audio or update.message.voice or update.message.document).file_id
    context.user_data["audio"] = fid
    has_both = "video" in context.user_data and "audio" in context.user_data

    if has_both:
        await update.message.reply_text("✅ Music saved! + Video already saved! Ready to edit?", reply_markup=menu(True))
    else:
        await update.message.reply_text("✅ Music saved! Now send the video clip")

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.data == "help":
        await q.message.reply_text("Send VIDEO first, then AUDIO MP3. When I have both, I will beat-sync edit.", reply_markup=menu("video" in context.user_data and "audio" in context.user_data))
        return

    if q.data != "edit":
        return

    if "video" not in context.user_data or "audio" not in context.user_data:
        await q.message.reply_text("You need to send BOTH video and music first!")
        return

    from moviepy import VideoFileClip, vfx, ColorClip, concatenate_videoclips, AudioFileClip
    import librosa

    status = await q.message.reply_text("🥁 Analyzing beats from your punk music...")

    with tempfile.TemporaryDirectory() as tmp:
        v_in = os.path.join(tmp, "v.mp4")
        a_in = os.path.join(tmp, "a.mp3")
        out = os.path.join(tmp, "out.mp4")

        vf = await context.bot.get_file(context.user_data["video"])
        af = await context.bot.get_file(context.user_data["audio"])
        await vf.download_to_drive(v_in)
        await af.download_to_drive(a_in)

        def do_edit():
            # Load clips
            vclip = VideoFileClip(v_in)
            if vclip.w > 720:
                vclip = vclip.resized(width=720)
            
            aclip = AudioFileClip(a_in)
            dur = min(vclip.duration, aclip.duration, 15) # limit 15s
            
            vclip = vclip.subclipped(0, dur)
            aclip = aclip.subclipped(0, dur)

            # BEAT DETECTION from YOUR music
            y, sr = librosa.load(a_in, duration=dur)
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr)
            
            # BUILD EDIT ON BEATS
            clips = []
            last = 0
            for i, bt in enumerate(beat_times):
                if bt >= dur or bt <= last:
                    continue
                # segment up to beat
                seg = vclip.subclipped(last, bt)
                # Velocity punch on beat - no hardcoded slow/fast, just punch
                if i % 2 == 0:
                    seg = seg.with_effects([vfx.MultiplySpeed(1.6)])
                else:
                    seg = seg.with_effects([vfx.MultiplySpeed(0.9)])
                clips.append(seg)
                # Flash transition on strong beats
                if i % 2 == 0:
                    clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.07))
                last = bt
            
            if last < dur:
                clips.append(vclip.subclipped(last, dur))

            final = concatenate_videoclips(clips) if clips else vclip
            final = final.with_audio(aclip)

            # BASELINE FIX FOR YOUR REDMI MTK
            final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None,
                ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2","-b:v","2500k","-maxrate","2500k","-bufsize","5000k"])
            
            vclip.close()
            aclip.close()
            final.close()
            return len(beat_times)

        beat_count = await asyncio.to_thread(do_edit)
        
        await status.edit_text(f"📤 Found {beat_count} beats - Uploading...")
        await q.message.reply_video(
            video=open(out, 'rb'), 
            caption=f"✅ Beat Sync Done - {beat_count} cuts on beat",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Edit Again", callback_data="edit")]])
        )
        await status.delete()
        # Keep files for re-edit
        # context.user_data.clear()

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_button))
    print("V7 Beat Sync Running")
    app.run_polling()
