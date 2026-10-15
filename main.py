import os, tempfile, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 OPERATOR Bot Ready!\nSend me a gaming clip and I will add:\n- Velocity Ramp\n- OPERATOR Slow-mo Finisher")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only for new moviepy 2.x
    try:
        from moviepy import VideoFileClip, vfx
    except:
        from moviepy.editor import VideoFileClip
        from moviepy.video.fx import all as vfx

    status_msg = await update.message.reply_text("⏳ Downloading video...")
    
    file = await context.bot.get_file(update.message.video or update.message.document)
    
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "in.mp4")
        out_path = os.path.join(tmp, "out.mp4")
        
        await file.download_to_drive(in_path)
        await status_msg.edit_text("⚡ Applying OPERATOR velocity...")

        # Run moviepy in thread so bot doesn't freeze
        def process():
            clip = VideoFileClip(in_path)
            duration = clip.duration
            
            # 1. VELOCITY RAMP: Normal -> 1.8x fast -> slow-mo at end
            # Last 20% = OPERATOR slow-mo finisher (0.4x speed)
            slow_start = duration * 0.75
            
            def speed_func(t):
                if t < duration * 0.4:
                    return 1.0  # normal start
                elif t < slow_start:
                    return 1.9  # velocity ramp fast middle
                else:
                    return 0.35  # OPERATOR ultra slow-mo finisher
            
            # Apply time effect
            # For moviepy 2.x use with_effects, for 1.x use fx
            try:
                # moviepy 2.1.2 way
                ramped = clip.with_effects([vfx.MultiplySpeed(speed_func)])
            except:
                ramped = clip.fx(vfx.time_mirror, lambda t: t) # fallback
                # Manual speed ramp simple: cut and speed
                part1 = clip.subclip(0, duration*0.4)
                part2 = clip.subclip(duration*0.4, slow_start).fx(vfx.speedx, 1.9)
                part3 = clip.subclip(slow_start, duration).fx(vfx.speedx, 0.35)
                from moviepy.editor import concatenate_videoclips
                ramped = concatenate_videoclips([part1, part2, part3])
            
            ramped.write_videofile(out_path, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
            clip.close()
            ramped.close()
        
        await asyncio.to_thread(process)
        
        await status_msg.edit_text("📤 Uploading finished clip...")
        await update.message.reply_video(video=open(out_path, 'rb'), caption="✅ OPERATOR Edit Done - Velocity + Slow-mo Finisher")
        await status_msg.delete()

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO | filters.Document.MimeType("video/mp4"), handle_video))
    print("OPERATOR Bot V2 starting...")
    app.run_polling()
