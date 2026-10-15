import os, tempfile, asyncio, traceback, random, numpy as np, requests, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION=20
YOUTUBE_COOKIES=os.getenv("YOUTUBE_COOKIES","") # optional, paste cookies.txt content

def menu(v=0,a=False):
    kb=[]
    if v>0 and a: kb.append([InlineKeyboardButton(f"🔥 SMART Edit V24.5 ({v} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {v} | Audio: {'Yes' if a else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    context.user_data["videos"]=[]; context.user_data["search_results"]=[]; context.user_data["direct_audio_path"]=None
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text(
        "👋 V24.5 - DIRECT YOUTUBE MODE\n\n"
        "NEW WAY (best):\nJust send YouTube link: https://youtu.be/xxx\nBot downloads direct on Railway, no need to upload mp3\n\n"
        "OLD WAY still works:\n1. Send videos as FILE\n2. /search burna boy\n\n"
        "Then click SMART Edit",
        reply_markup=menu())

async def on_video(update, context):
    if "videos" not in context.user_data: context.user_data["videos"]=[]
    fid=(update.message.video or update.message.document).file_id
    context.user_data["videos"].append(fid)
    v=len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Video {v} added", reply_markup=menu(v, "audio" in context.user_data or context.user_data.get("direct_audio_path")))

async def on_audio(update, context):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    context.user_data["direct_audio_path"]=None
    v=len(context.user_data.get("videos",[]))
    await update.message.reply_text(f"✅ Audio saved from Telegram", reply_markup=menu(v, True))

# DIRECT YOUTUBE LINK HANDLER - YOUR IDEA
async def on_youtube_link(update, context):
    url=update.message.text.strip()
    # extract video id
    m=re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,})', url)
    if not m: return
    video_id=m.group(1)
    status=await update.message.reply_text(f"⬇️ Direct download on Railway: {video_id}...\nNo need to upload to Telegram, I'm getting audio direct...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmp:
            cookie_file=None
            if YOUTUBE_COOKIES:
                cookie_file=os.path.join(tmp,"cookies.txt")
                open(cookie_file,'w', encoding='utf-8').write(YOUTUBE_COOKIES)

            # This is the bypass: use android, ios clients - works without login for most
            ydl_opts={
                'format':'bestaudio/best',
                'outtmpl':os.path.join(tmp,'direct_audio.%(ext)s'),
                'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}],
                'quiet':True,
                'no_warnings':True,
                'extractor_args':{'youtube':{'player_client':['android','ios','web']}},
            }
            if cookie_file: ydl_opts['cookiefile']=cookie_file

            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            await asyncio.to_thread(download)

            # find mp3
            mp3_path=None
            for f in os.listdir(tmp):
                if f.endswith(".mp3") or f.endswith(".m4a"):
                    mp3_path=os.path.join(tmp,f)
                    break
            if not mp3_path or not os.path.exists(mp3_path):
                await status.edit_text("❌ Direct download failed, YouTube blocked Railway IP. Try adding YOUTUBE_COOKIES in Railway Variables.\nOr use /search and try other song.")
                return

            # Save this file permanently for editing - upload to Telegram as file_id for reuse
            # We will store the file_id by uploading to telegram then saving
            # For now, save path in context and also send as audio to get file_id
            sent=await update.message.reply_audio(audio=open(mp3_path,'rb'), caption="✅ Direct download success! Setting as audio automatically...")
            context.user_data["audio"]=sent.audio.file_id
            context.user_data["direct_audio_path"]=None # using file_id now
            v=len(context.user_data.get("videos",[]))
            await status.edit_text(f"✅ Audio set directly from YouTube!\nNo need to re-upload. Now send videos and click SMART Edit", reply_markup=menu(v, True))

    except Exception as e:
        err=str(e)
        if "Sign in to confirm" in err or "bot" in err.lower():
            await status.edit_text(
                "❌ YouTube blocked Railway IP (Sign in to confirm you're not a bot).\n\n"
                "FIX 1: Go to Railway -> Variables -> Add YOUTUBE_COOKIES\n"
                "How to get cookies: Install 'Get cookies.txt LOCALLY' Chrome extension, go to youtube.com logged in, export, paste content into YOUTUBE_COOKIES variable.\n\n"
                "FIX 2: Try a different song, some songs are less blocked."
            )
        else:
            await status.edit_text(f"Direct download error: {err[:500]}")

def piped_download(video_id, out_path):
    # Keep as backup for /search buttons
    try:
        import yt_dlp
        ydl_opts={
            'format':'bestaudio/best',
            'outtmpl':out_path.replace('.mp3','.%(ext)s'),
            'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3'}],
            'quiet':True,
            'extractor_args':{'youtube':{'player_client':['android','ios']}},
        }
        if YOUTUBE_COOKIES:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as cf:
                cf.write(YOUTUBE_COOKIES)
                ydl_opts['cookiefile']=cf.name
        def dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        import asyncio as _a
        # sync call will be wrapped in to_thread outside
        dl()
        # find file
        base=os.path.splitext(out_path)[0]
        for ext in ['.mp3','.m4a','.webm','.mp4']:
            if os.path.exists(base+ext):
                if base+ext!=out_path:
                    os.rename(base+ext, out_path)
                return os.path.exists(out_path) and os.path.getsize(out_path)>1000
        return os.path.exists(out_path)
    except: return False

async def search_cmd(update, context):
    query=" ".join(context.args)
    if not query: return await update.message.reply_text("Use: /search burna boy OR send YouTube link directly")
    status=await update.message.reply_text(f"🔍 Searching YouTube: {query}...")
    try:
        import yt_dlp
        ydl_opts={'quiet':True,'skip_download':True,'extract_flat':True,'extractor_args':{'youtube':{'player_client':['android']}}}
        def do_search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch5:{query}", download=False)
        result=await asyncio.to_thread(do_search)
        entries=[e for e in result.get('entries',[]) if e][:5]
        if not entries:
            await status.edit_text("No results"); return
        context.user_data["search_results"]=entries
        buttons=[[InlineKeyboardButton(f"🎵 {e.get('title','')[:45]}", callback_data=f"yt_{i}")] for i,e in enumerate(entries)]
        buttons.append([InlineKeyboardButton("💡 Tip: Send YouTube link directly for best result", callback_data="status")])
        await status.edit_text("YouTube results (tap to download - now direct on Railway):", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e: await status.edit_text(f"Search error: {e}")

async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or ("audio" not in context.user_data):
        await update_msg.reply_text("Send video + audio first. For audio, just send YouTube link!"); return
    status=await update_msg.reply_text(f"⏳ V24.5 SMART processing...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            vfiles=[]
            for i,fid in enumerate(context.user_data["videos"]):
                p=os.path.join(tmp,f"v{i}.mp4"); f=await context.bot.get_file(fid); await f.download_to_drive(p); vfiles.append(p)
            a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            af=await context.bot.get_file(context.user_data["audio"]); await af.download_to_drive(a_in)
            def process():
                vclips=[VideoFileClip(p) for p in vfiles]; aclip=AudioFileClip(a_in); song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclips[0].size; cool=[]
                try:
                    import cv2
                    for vc in vclips:
                        for t in np.arange(0.3, max(0.4, vc.duration-0.7), 0.45):
                            try:
                                f1=vc.get_frame(t); f2=vc.get_frame(t+0.45)
                                if np.mean(f1)<10 or np.mean(f2)<10: continue
                                g1=cv2.cvtColor(f1, cv2.COLOR_RGB2GRAY); g2=cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                                move=np.mean(cv2.absdiff(g1,g2)); cool.append((vc,t,move))
                            except: continue
                    cool.sort(key=lambda x: x[2], reverse=True)
                    filt=[]; used=[]
                    for vc,t,s in cool:
                        if all(abs(t-u)>0.9 for u in used): filt.append((vc,t,s)); used.append(t)
                    cool=filt[:20]
                except:
                    for vc in vclips:
                        for i in range(8): cool.append((vc, i*0.8, 0))
                clips=[]; total=0; idx=0
                while total<song_dur and idx<len(cool):
                    vc,t,_=cool[idx]; idx+=1
                    if t+0.4>vc.duration: continue
                    seg=vc.subclip(t, t+0.38).resize((W,H))
                    zoom=1.35
                    if idx<=4:
                        seg_z=seg.resize(zoom).crop(x_center=W/2+random.randint(-10,10), y_center=H/2, width=W, height=H).fx(vfx.speedx, 2.0)
                        clips.append(seg_z); clips.append(seg_z.fx(vfx.time_mirror)); total+=0.76
                    else:
                        seg_z=seg.resize(zoom).crop(x_center=W/2, y_center=H/2, width=W, height=H).fx(vfx.speedx, random.uniform(1.7,2.1))
                        clips.append(seg_z); total+=0.38
                merged=concatenate_videoclips(clips, method="compose")
                if merged.duration<song_dur: merged=merged.loop(duration=song_dur+0.2)
                final_main=merged.subclip(0, song_dur).crop(y1=int(H*0.08), y2=H, x1=0, x2=W).resize((W,H))
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.03), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.5)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except: final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None, ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"])
                for vc in vclips: vc.close(); aclip.close(); final.close(); merged.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V24.5 Direct YouTube mode")
            await status.delete()
    except Exception as e: await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-800:]}")

async def on_btn(update, context):
    q=update.callback_query; await q.answer()
    d=q.data
    if d=="edit": await do_edit(q.message, context)
    elif d=="clear":
        context.user_data["videos"]=[]; context.user_data["search_results"]=[]
        if "audio" in context.user_data: del context.user_data["audio"]
        await q.message.edit_text("🗑 Cleared", reply_markup=menu(0,False))
    elif d.startswith("yt_"):
        try:
            idx=int(d.split("_")[1])
            entries=context.user_data.get("search_results",[])
            item=entries[idx]
            video_id=item.get('id')
            if not video_id:
                url=item.get('url','')
                video_id=url.split('v=')[-1] if 'v=' in url else url.split('/')[-1]
            status=await q.message.reply_text(f"⬇️ Direct Railway download: {item.get('title','')[:40]}...\nNo Piped, direct yt-dlp...")
            with tempfile.TemporaryDirectory() as tmp:
                mp3_path=os.path.join(tmp,"song.mp3")
                ok=await asyncio.to_thread(piped_download, video_id, mp3_path)
                if ok and os.path.exists(mp3_path) and os.path.getsize(mp3_path)>1000:
                    sent=await q.message.reply_audio(audio=open(mp3_path,'rb'), title=item.get('title','')[:40], caption="✅ Downloaded direct on Railway! Audio set!")
                    context.user_data["audio"]=sent.audio.file_id
                    await status.delete()
                else:
                    await status.edit_text(f"Direct download blocked for {video_id}. SOLUTION: Send YouTube link directly like https://youtu.be/{video_id} - it uses better bypass. Or add YOUTUBE_COOKIES variable in Railway.")
        except Exception as e: await q.message.reply_text(f"Fail: {e}")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    # YouTube link handler must be before generic text
    app.add_handler(MessageHandler(filters.Regex(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)'), on_youtube_link))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.run_polling()
if __name__=="__main__": main()
