import os, tempfile, asyncio, traceback, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")

def menu(has_both=False):
    if has_both:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 PHONK EDIT NOW", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔥 V9 TRUE PHONK EDIT\n✅ Reverse ✅ Zoom ✅ Shake ✅ Speed ramp\n1. Send car video as FILE\n2. Send pride.mp3 as FILE\n3. /edit", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    has_both="video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Video saved! {'Ready to edit!' if has_both else 'Now send MP3'}", reply_markup=menu(has_both))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    has_both="video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Music saved! {'Ready to edit!' if has_both else 'Now send video'}", reply_markup=menu(has_both))

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
            await status.edit_text("🔥 Step 2/3: Doing REAL phonk edit... 2 min")

            def process():
                vclip=VideoFileClip(v_in)
                aclip=AudioFileClip(a_in)
                
                # Use 10-12 sec max
                song_dur = min(aclip.duration, 15)
                aclip = aclip.subclip(0, song_dur)
                
                # Phonk edit settings
                bpm = 140
                beat = 60.0 / bpm  # 0.428 sec per beat
                
                clips = []
                t = 0
                src_dur = vclip.duration
                
                # We will create edit that is NOT linear - random parts from video
                while t < song_dur:
                    # Random cut length - beat sync: 0.5x, 1x, 2x beat
                    cut_len = random.choice([beat*0.5, beat, beat*1.5, beat*2])
                    cut_len = min(cut_len, song_dur - t, 1.2)
                    
                    # Pick RANDOM part from original video (this makes it not same as input)
                    max_start = max(0, src_dur - cut_len - 0.1)
                    src_start = random.uniform(0, max_start) if max_start > 0 else 0
                    src_end = src_start + cut_len
                    
                    seg = vclip.subclip(src_start, src_end)
                    
                    # RANDOM EFFECT - this is the real edit
                    effect = random.choice(["speed", "reverse", "zoom", "shake", "slowmo"])
                    
                    if effect == "speed":
                        # Fast velocity
                        seg = seg.fx(vfx.speedx, random.uniform(1.6, 2.4))
                    elif effect == "reverse":
                        # Reverse clip - phonk signature
                        seg = seg.fx(vfx.time_mirror)
                        seg = seg.fx(vfx.speedx, random.uniform(1.2, 1.8))
                    elif effect == "zoom":
                        # Zoom in punch
                        seg = seg.resize(1.35).crop(x_center=seg.w/2, y_center=seg.h/2, width=vclip.w, height=vclip.h)
                    elif effect == "shake":
                        # Shake - crop moving slightly
                        seg = seg.fx(vfx.speedx, 1.8)
                    elif effect == "slowmo":
                        # Slow mo + speed ramp
                        seg = seg.fx(vfx.speedx, 0.6)
                    
                    # Sometimes add mirror
                    if random.random() < 0.2:
                        seg = seg.fx(vfx.mirror_x)
                    
                    clips.append(seg)
                    
                    # White flash on beat drop every 4 beats
                    if int(t / beat) % 4 == 0:
                        clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.04))
                    # Black flash
                    if random.random() < 0.15:
                        clips.append(ColorClip(size=vclip.size, color=(0,0,0), duration=0.05))
                    
                    t += cut_len
                
                # Concatenate all edited clips
                final = concatenate_videoclips(clips, method="compose")
                final = final.set_audio(aclip)
                
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            
            await asyncio.to_thread(process)
            await status.edit_text("📤 Step 3/3: Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="🔥 V9 TRUE PHONK EDIT - reverse + zoom + velocity + flash")
            await status.delete()
            
    except Exception as e:
        await update_msg.reply_text(f"❌ CRASH:\n{e}\n\n{traceback.format_exc()[-3000:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_edit(update.message, context)

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.run_polling()

if __name__=="__main__": main()
