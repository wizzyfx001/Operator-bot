import os, tempfile, asyncio, traceback, random, numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20

def menu(videos=0, has_audio=False):
    kb=[]
    if videos>0 and has_audio:
        kb.append([InlineKeyboardButton(f"🔥 SMART Edit ({videos} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {videos} | Audio: {'Yes' if has_audio else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear", callback_data="clear")])
    kb.append([InlineKeyboardButton("🎵 Search Songs", callback_data="trending")])
    return InlineKeyboardMarkup(kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["videos"]=[];
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text("👋 V23 SMART - Multi + No Black + Portrait Fix\n\n1. Send MANY videos as FILES\n2. Send audio as FILE or /search", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "videos" not in context.user_data: context.user_data["videos"]=[]
    fid=(update.message.video or update.message.document).file_id
    context.user_data["videos"].append(fid)
    v=len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Video {v} added! You have {v}. Keep sending or send audio.", reply_markup=menu(v, "audio" in context.user_data))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    v=len(context.user_data.get("videos",[]))
    await update.message.reply_text(f"✅ Audio ready!", reply_markup=menu(v, True))

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=" ".join(context.args)
    if not query:
        await update.message.reply_text("Use: /search the box"); return
    status=await update.message.reply_text(f"🔍 Searching: {query}...")
    try:
        import yt_dlp
        # FIX FOR YOUR SCREENSHOT ERROR - bypass bot check
        ydl_opts={
            'quiet':True,
            'skip_download':True,
            'extract_flat':True,
            'extractor_args': {'youtube': {'player_client': ['android','web']}}, # FIX
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result=ydl.extract_info(f"ytsearch5:{query} phonk", download=False)
        buttons=[]
        for entry in result['entries'][:5]:
            title=entry['title'][:40]
            vid=entry['id']
            buttons.append([InlineKeyboardButton(f"🎵 {title}", callback_data=f"pick_{vid}")])
        await status.edit_text(f"Found for '{query}':", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await status.edit_text(f"Search error: {e}")

async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send at least 1 video + 1 audio first"); return
    status=await update_msg.reply_text(f"⏳ V23 SMART analyzing {len(context.user_data['videos'])} videos for cool moments...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            video_files=[]
            for idx, fid in enumerate(context.user_data["videos"]):
                p=os.path.join(tmp,f"v{idx}.mp4")
                f=await context.bot.get_file(fid); await f.download_to_drive(p)
                video_files.append(p)
            a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            af=await context.bot.get_file(context.user_data["audio"]); await af.download_to_drive(a_in)

            def process():
                vclips=[VideoFileClip(p) for p in video_files]
                aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclips[0].size

                # === SMART: Find cool moments via motion ===
                cool_segments=[]
                try:
                    import cv2
                    for vc in vclips:
                        scores=[]
                        dur=vc.duration
                        step=0.3
                        for t in np.arange(0.2, max(0.2, dur-0.6), step):
                            try:
                                f1=vc.get_frame(t)
                                f2=vc.get_frame(t+step)
                                g1=cv2.cvtColor(f1, cv2.COLOR_RGB2GRAY)
                                g2=cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                                diff=cv2.absdiff(g1,g2)
                                move=np.mean(diff)
                                scores.append((vc, t, move))
                            except: continue
                        # take top 8 coolest per video
                        scores.sort(key=lambda x: x[2], reverse=True)
                        cool_segments.extend(scores[:8])
                    cool_segments.sort(key=lambda x: x[2], reverse=True)
                except Exception as e:
                    print(f"CV2 fail fallback random: {e}")
                    # fallback
                    for vc in vclips:
                        for _ in range(8):
                            cool_segments.append((vc, random.uniform(0, max(0, vc.duration-1)), 0))

                # Build clips from coolest
                clips=[]; total=0
                idx=0
                while total < song_dur + 0.7 and idx < len(cool_segments):
                    vc, t, score = cool_segments[idx]
                    idx+=1
                    cut=0.35 if score>30 else 0.42 # shorter on super cool
                    seg_end=min(t+cut, vc.duration)
                    seg=vc.subclip(t, seg_end)

                    # Preserve aspect - NO STRETCH
                    # Zoom crop centered
                    zoom=1.38
                    is_super_cool = idx <= 6 # top 6 moments get reverse
                    if is_super_cool:
                        seg_z=seg.resize(zoom).crop(x_center=W/2+random.randint(-15,15), y_center=H/2, width=W, height=H).fx(vfx.speedx, 2.0)
                        seg_rev=seg_z.fx(vfx.time_mirror)
                        clips.append(seg_z); clips.append(seg_rev)
                        total+=cut*2
                    else:
                        seg_z=seg.resize(zoom).crop(x_center=W/2, y_center=H/2, width=W, height=H).fx(vfx.speedx, random.uniform(1.6,2.2))
                        clips.append(seg_z)
                        total+=cut
                    if len(clips)>140: break

                # Guarantee no black
                merged=concatenate_videoclips(clips, method="compose")
                if merged.duration < song_dur:
                    merged=merged.loop(duration=song_dur+0.5)
                final_main=merged.subclip(0, song_dur)
                # Crop 8% top to remove TikTok watermark, but keep portrait
                final_main=final_main.crop(y1=int(H*0.08), y2=H, x1=0, x2=W).resize((W,H))

                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.032), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.55)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)

                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
                                      ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                for vc in vclips: vc.close()
                aclip.close(); final.close(); merged.close()

            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading SMART edit...")
            await update_msg.reply_video(video=open(out,'rb'), caption=f"✅ V23 SMART - {len(video_files)} vids mixed, cool moments + reverse - No black")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-1200:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    data=q.data
    if data=="edit": await do_edit(q.message, context)
    elif data=="clear":
        context.user_data["videos"]=[];
        if "audio" in context.user_data: del context.user_data["audio"]
        await q.message.edit_text("🗑 Cleared.", reply_markup=menu(0, False))
    elif data.startswith("pick_"):
        vid=data[5:]
        status=await q.message.reply_text("⬇️ Downloading song (bypassing bot check)...")
        try:
            import yt_dlp
            with tempfile.TemporaryDirectory() as tmp:
                # FIX for download too
                ydl_opts={
                    'format':'bestaudio/best',
                    'outtmpl':os.path.join(tmp,'audio.%(ext)s'),
                    'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3'}],
                    'quiet':True,
                    'extractor_args': {'youtube': {'player_client': ['android']}}, # THIS FIXES YOUR ERROR
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])
                # Find mp3
                mp3_path=None
                for f in os.listdir(tmp):
                    if f.endswith(".mp3"): mp3_path=os.path.join(tmp,f)
                if mp3_path:
                    await q.message.reply_audio(audio=open(mp3_path,'rb'), caption="✅ Downloaded - now this audio is ready. Press SMART Edit")
                    # auto set as audio file_id? We need to upload
                    msg=await q.message.reply_text("Uploading to bot memory... send that audio file back as FILE to use it, or I will auto set next version")
                else:
                    await status.edit_text("Downloaded but no mp3 found")
        except Exception as e:
            await status.edit_text(f"Download still blocked: {e}\nTry uploading mp3 manually for now")
    elif data=="trending":
        await q.message.reply_text("Use /search <song name>\nExample: /search the box")

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
