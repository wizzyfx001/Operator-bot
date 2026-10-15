import os, tempfile, asyncio, traceback, random, numpy as np, requests
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
        kb.append([InlineKeyboardButton(f"🔥 SMART Edit V23.3 ({videos} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {videos} | Audio: {'Yes' if has_audio else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear All", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["videos"]=[]
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text(f"👋 V23.3 FINAL - No Cookies Needed, No Black, No Repeat\n\nSend MANY videos as FILE\nThen /search (now uses bypass)\n\nAuto: finds dunks/drifts, adds reverse", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "videos" not in context.user_data: context.user_data["videos"]=[]
    fid=(update.message.video or update.message.document).file_id
    context.user_data["videos"].append(fid)
    v=len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Video {v} added! Total {v}", reply_markup=menu(v, "audio" in context.user_data))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    v=len(context.user_data.get("videos",[]))
    await update.message.reply_text(f"✅ Audio ready!", reply_markup=menu(v, True))

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=" ".join(context.args)
    if not query: return await update.message.reply_text("Use: /search the box")
    status=await update.message.reply_text(f"🔍 Searching: {query}...")
    try:
        import yt_dlp
        # Use android client only - works for search, no cookies needed for search
        ydl_opts={'quiet':True,'skip_download':True,'extract_flat':True,'extractor_args':{'youtube':{'player_client':['android']}}}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result=ydl.extract_info(f"ytsearch5:{query} phonk", download=False)
        buttons=[[InlineKeyboardButton(f"🎵 {e['title'][:40]}", callback_data=f"pick_{e['id']}")] for e in result['entries'][:5]]
        await status.edit_text("Found (download via bypass, no cookies needed):", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e: await status.edit_text(f"Search error: {e}")

def download_via_cobalt(youtube_id, out_path):
    # Cobalt bypass - no YouTube login needed, works on Railway
    try:
        url=f"https://www.youtube.com/watch?v={youtube_id}"
        # Try public cobalt instances
        for api in ["https://api.cobalt.tools", "https://co.wuk.sh"]:
            try:
                r=requests.post(f"{api}/api/json", json={"url": url, "isAudioOnly": True, "aFormat": "mp3"}, headers={"Accept":"application/json"}, timeout=15)
                data=r.json()
                if "url" in data:
                    audio_url=data["url"]
                    # download mp3
                    rr=requests.get(audio_url, stream=True, timeout=30)
                    with open(out_path, 'wb') as f:
                        for chunk in rr.iter_content(8192): f.write(chunk)
                    return True
            except Exception as e:
                print(f"Cobalt {api} failed {e}")
                continue
        return False
    except Exception as e:
        print(f"Cobalt error {e}"); return False

async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send at least 1 video + 1 audio"); return
    status=await update_msg.reply_text(f"⏳ V23.3 SMART analyzing {len(context.user_data['videos'])} videos - no black fix...")
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

            def is_black(frame):
                return np.mean(frame) < 10 if frame is not None else True

            def process():
                vclips=[VideoFileClip(p) for p in video_files]
                aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclips[0].size; TARGET_W, TARGET_H=W,H
                cool_segments=[]
                try:
                    import cv2
                    for vc in vclips:
                        scores=[]
                        for t in np.arange(0.3, max(0.4, vc.duration-0.7), 0.4):
                            try:
                                f=vc.get_frame(t); f2=vc.get_frame(t+0.4)
                                if is_black(f) or is_black(f2): continue
                                g1=cv2.cvtColor(f, cv2.COLOR_RGB2GRAY); g2=cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                                move=np.mean(cv2.absdiff(g1,g2))
                                if any(abs(t - pt) < 0.8 for _, pt, _ in scores): continue
                                scores.append((vc, t, move))
                            except: continue
                        scores.sort(key=lambda x: x[2], reverse=True)
                        cool_segments.extend(scores[:10])
                    cool_segments.sort(key=lambda x: x[2], reverse=True)
                    filtered=[]; used=[]
                    for vc,t,s in cool_segments:
                        if all(abs(t-u)>0.8 for u in used):
                            filtered.append((vc,t,s)); used.append(t)
                    cool_segments=filtered[:20]
                except:
                    for vc in vclips:
                        for i in range(10): cool_segments.append((vc, i*0.9, 0))

                clips=[]; total=0; idx=0
                while total < song_dur and idx < len(cool_segments):
                    vc,t,_=cool_segments[idx]; idx+=1
                    if t+0.5>vc.duration: continue
                    seg=vc.subclip(t, t+0.38).resize((TARGET_W, TARGET_H))
                    try:
                        if is_black(seg.get_frame(0.05)): continue
                    except: pass
                    zoom=1.33
                    if idx<=4:
                        seg_z=seg.resize(zoom).crop(x_center=TARGET_W/2+random.randint(-12,12), y_center=TARGET_H/2, width=TARGET_W, height=TARGET_H).fx(vfx.speedx, 2.0)
                        clips.append(seg_z); clips.append(seg_z.fx(vfx.time_mirror)); total+=0.76
                    else:
                        seg_z=seg.resize(zoom).crop(x_center=TARGET_W/2, y_center=TARGET_H/2, width=TARGET_W, height=TARGET_H).fx(vfx.speedx, random.uniform(1.7,2.1))
                        clips.append(seg_z); total+=0.38
                    if len(clips)>60: break

                merged=concatenate_videoclips(clips, method="compose")
                if merged.duration < song_dur: merged=merged.loop(duration=song_dur+0.2)
                final_main=merged.subclip(0, song_dur).crop(y1=int(TARGET_H*0.08), y2=TARGET_H, x1=0, x2=TARGET_W).resize((TARGET_W, TARGET_H))
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(TARGET_H*0.032), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.55)
                    final=CompositeVideoClip([final_main, wm], size=(TARGET_W, TARGET_H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None, ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"])
                for vc in vclips: vc.close()
                aclip.close(); final.close(); merged.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V23.3 - No black, no repeat, no cookies needed")
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
        await q.message.edit_text("🗑 Cleared", reply_markup=menu(0, False))
    elif data.startswith("pick_"):
        vid=data[5:]; status=await q.message.reply_text("⬇️ Downloading via bypass (no cookies)...")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                mp3_path=os.path.join(tmp,"song.mp3")
                ok=await asyncio.to_thread(download_via_cobalt, vid, mp3_path)
                if ok and os.path.exists(mp3_path):
                    await q.message.reply_audio(audio=open(mp3_path,'rb'), title="Phonk", caption="✅ Bypass success! Now SEND THIS FILE BACK AS FILE to set it as audio")
                    await status.delete()
                else:
                    # Fallback try yt-dlp android
                    try:
                        import yt_dlp
                        ydl_opts={'format':'bestaudio/best','outtmpl':os.path.join(tmp,'audio.%(ext)s'),'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3'}],'quiet':True,'extractor_args':{'youtube':{'player_client':['android']}}}
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([f"https://www.youtube.com/watch?v={vid}"])
                        for f in os.listdir(tmp):
                            if f.endswith(".mp3"):
                                mp3_path=os.path.join(tmp,f)
                                await q.message.reply_audio(audio=open(mp3_path,'rb'), caption="✅ Downloaded via android client")
                                await status.delete(); return
                        await status.edit_text("Both bypass failed, try uploading mp3 manually")
                    except Exception as e2:
                        await status.edit_text(f"Bypass failed: {e2}\nTry another song or upload mp3 manually")
        except Exception as e:
            await status.edit_text(f"Error: {e}")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
