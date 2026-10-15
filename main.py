import os, tempfile, asyncio, traceback, random, numpy as np, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION=20

def menu(v=0,a=False):
    kb=[]
    if v>0 and a: kb.append([InlineKeyboardButton(f"🔥 SMART Edit V24.2 ({v} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {v} | Audio: {'Yes' if a else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    context.user_data["videos"]=[]; context.user_data["search_results"]=[]
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text("👋 V24.2 Piped - Works for Naija + Foreign\n\n1. Send videos as FILE\n2. /search burna boy or /search eloy", reply_markup=menu())

async def on_video(update, context):
    if "videos" not in context.user_data: context.user_data["videos"]=[]
    fid=(update.message.video or update.message.document).file_id
    context.user_data["videos"].append(fid)
    v=len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Video {v} added", reply_markup=menu(v, "audio" in context.user_data))

async def on_audio(update, context):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    v=len(context.user_data.get("videos",[]))
    await update.message.reply_text(f"✅ Audio saved", reply_markup=menu(v, True))

def piped_search(query):
    # Use Piped API to search YouTube - bypasses bot check
    try:
        for instance in ["https://pipedapi.kavin.rocks", "https://api.piped.projectsegfau.lt", "https://pipedapi.adminforge.de"]:
            try:
                r=requests.get(f"{instance}/search", params={"q": query}, timeout=15)
                data=r.json()
                items=[x for x in data.get('items',[]) if x.get('type')=='stream'][:5]
                if items: return items
            except: continue
        return []
    except: return []

def piped_download(video_id, out_path):
    # Get audio stream from Piped
    for instance in ["https://pipedapi.kavin.rocks", "https://api.piped.projectsegfau.lt", "https://pipedapi.adminforge.de"]:
        try:
            r=requests.get(f"{instance}/streams/{video_id}", timeout=15)
            data=r.json()
            # get best audio
            audios=data.get('audioStreams',[])
            if not audios: continue
            # pick mp3/m4a highest quality
            audio_url=sorted(audios, key=lambda x: x.get('bitrate',0), reverse=True)[0]['url']
            rr=requests.get(audio_url, stream=True, timeout=30)
            with open(out_path, 'wb') as f:
                for chunk in rr.iter_content(8192): f.write(chunk)
            return True
        except Exception as e:
            print(f"Piped {instance} fail {e}"); continue
    return False

async def search_cmd(update, context):
    query=" ".join(context.args)
    if not query: return await update.message.reply_text("Use: /search burna boy")
    status=await update.message.reply_text(f"🔍 Piped YouTube search: {query}...")
    try:
        items=await asyncio.to_thread(piped_search, query)
        if not items:
            await status.edit_text("No results, try different keyword or check spelling"); return
        context.user_data["search_results"]=items
        buttons=[]
        for i,e in enumerate(items):
            title=e.get('title','Unknown')[:45]
            buttons.append([InlineKeyboardButton(f"🎵 {title}", callback_data=f"yt_{i}")])
        await status.edit_text("YouTube results via Piped (Naija + foreign, no DRM):", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e: await status.edit_text(f"Search error: {e}")

async def do_edit(update_msg, context):
    # same smart edit as before, no black, no repeat
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send video + audio first"); return
    status=await update_msg.reply_text(f"⏳ V24.2 SMART processing...")
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
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V24.2 - Naija + Foreign OK")
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
            if idx>=len(entries): await q.message.reply_text("Search again, expired"); return
            item=entries[idx]
            video_id=item.get('url','').split('=')[-1].split('/')[-1] if 'v=' in item.get('url','') else item.get('url','').split('/')[-1]
            # Piped items have url like /watch?v=xxxx
            if 'watch?v=' in item.get('url',''): video_id=item['url'].split('v=')[-1]
            else: video_id=item.get('url','').split('/')[-1]
            status=await q.message.reply_text(f"⬇️ Downloading via Piped: {item.get('title','')[:30]}...")
            with tempfile.TemporaryDirectory() as tmp:
                mp3_path=os.path.join(tmp,"song.mp3")
                ok=await asyncio.to_thread(piped_download, video_id, mp3_path)
                if ok and os.path.exists(mp3_path) and os.path.getsize(mp3_path)>1000:
                    await q.message.reply_audio(audio=open(mp3_path,'rb'), title=item.get('title',''), caption="✅ Downloaded! SEND THIS FILE BACK AS FILE to set as audio")
                    await status.delete()
                else:
                    await status.edit_text("Piped failed, try another song or try again in 10 sec (Piped busy)")
        except Exception as e: await q.message.reply_text(f"Download fail: {e}")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.run_polling()
if __name__=="__main__": main()
