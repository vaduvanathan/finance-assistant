import streamlit as st
import requests
import time
import yfinance as yf
import string
import fitz  # PyMuPDF for PDF processing
import base64
import io
from gtts import gTTS

st.set_page_config(page_title="Finance Voice & Document Assistant", layout="wide")
st.title("🎙️ Multi-Source Finance Assistant")

# ——————————————————————————————
# API KEYS (hard-coded for now)
ASSEMBLYAI_API_KEY = "a5c865ecb6cd4152ad9c91564a753cd2"
FMP_API_KEY        = "vLJtmE98fFBnb8zw65y0Sl9yJjmB2u9Q"
ASSEMBLYAI_HEADERS = {"authorization": ASSEMBLYAI_API_KEY}
# ——————————————————————————————

# ——————————————————————————————
# 1) Keyword extraction (for stock search)
def extract_possible_company_names(text):
    text = text.translate(str.maketrans("", "", string.punctuation))
    words = text.split()
    stopwords = {
        "the","what","about","is","stock","market","price","update",
        "how","in","to","and","of","a","an","can","you","give","me",
        "tell","show","today","quote","value","exchange","it","doing",
        "for","report","news","brief","summary","daily","weekly","change",
        "percent","at","on","up","down","high","low","open","close","last",
        "morning","afternoon","evening","today's","yesterday's","current",
        "companies","company","shares","indices","index","group","holdings",
        "performance","analysis","latest","find","out","about","looking",
        "which","are","these","those","any","some","get","please"
    }
    return [w for w in words if w.lower() not in stopwords and len(w)>2]

# 2) FMP search (with rate-limit handling)
def search_stock_symbol_fmp(keyword):
    url = f"https://financialmodelingprep.com/api/v3/search?query={keyword}&limit=1&apikey={FMP_API_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        results = res.json()
        if results:
            return results[0]["symbol"]
        return None
    if res.status_code == 429:
        st.error("❌ FMP API rate-limit exceeded. Aborting further searches.")
        return "RATE_LIMIT_EXCEEDED"
    st.warning(f"FMP search error ({res.status_code})")
    return None

# 3) Stock summary + analytics
def get_stock_summary(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        if not info or not info.get("regularMarketPrice"):
            return {"error": f"No data for {symbol}"}
        hist = t.history(period="7d")
        if hist.empty:
            hist = t.history(period="1d")
        current = info.get("currentPrice", hist["Close"].iloc[-1])
        prev_close = hist["Close"].iloc[-2] if len(hist)>=2 else info.get("previousClose", current)
        daily_pct = (current - prev_close)/prev_close*100 if prev_close else 0
        week_old = hist["Close"].iloc[0]
        weekly_pct = (current - week_old)/week_old*100 if week_old else 0
        return {
            "name": info.get("longName", symbol),
            "symbol": symbol,
            "price": current,
            "daily_pct": round(daily_pct,2),
            "weekly_pct": round(weekly_pct,2),
            "trend": "up 📈" if weekly_pct>0 else "down 📉" if weekly_pct<0 else "unchanged"
        }
    except Exception as e:
        return {"error": str(e)}

# 4) PDF extraction + chunking
def extract_text_from_pdf(pdf_file):
    try:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        st.error(f"PDF read error: {e}")
        return ""

def chunk_text(text, size=300, overlap=50):
    tokens = text.split()
    chunks=[]
    i=0
    while i<len(tokens):
        chunk = tokens[i:i+size]
        chunks.append(" ".join(chunk))
        i += size-overlap
    return chunks

# 5) Text-to-Speech (optional)
def text_to_audio(text):
    try:
        buf = io.BytesIO()
        gTTS(text=text, lang="en", slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except:
        return None

# ——————————————————————————————
# Layout: two columns
col1, col2 = st.columns(2)

# —— COLUMN 1: Voice Query Analysis ——
with col1:
    st.subheader("🎤 Voice Query Analysis")
    # 1a) MP3 upload fallback
    audio_upload = st.file_uploader("Upload MP3 (or record below)", type=["mp3"])
    # 1b) Simple JS recorder (as before)
    st.markdown("**Or record live:**")
    st.components.v1.html("""
    <button onclick="start()">Start</button><button onclick="stop()">Stop</button>
    <script>
        let rec, stream;
        async function start(){
            stream=await navigator.mediaDevices.getUserMedia({audio:true});
            rec=new MediaRecorder(stream);
            let data=[];
            rec.ondataavailable=e=>data.push(e.data);
            rec.onstop=async()=>{
                let blob=new Blob(data,{type:"audio/webm"});
                let r=new FileReader();
                r.onloadend=()=>window.parent.postMessage({ 
                    type:'streamlit:setComponentValue', key:'audio_rec', value:r.result 
                },'*');
                r.readAsDataURL(blob);
            };
            rec.start();
        }
        function stop(){rec.stop(); stream.getTracks().forEach(t=>t.stop());}
    </script>
    """, height=100)

    # 1c) Session state holds base64
    recorded = st.session_state.get("audio_rec", None)
    use_audio = None
    if audio_upload:
        use_audio = audio_upload.read()
    elif isinstance(recorded, str) and recorded.startswith("data:audio"):
        use_audio = base64.b64decode(recorded.split(",",1)[1])

    # Always show button once we have some audio data
    if use_audio:
        st.success("✅ Audio ready. Click below to transcribe.")
        if st.button("Transcribe & Fetch Stock"):
            # Upload to AssemblyAI
            r = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=ASSEMBLYAI_HEADERS,
                files={"file": ("audio.webm", use_audio, "audio/webm")}
            )
            if r.status_code!=200:
                st.error("Audio upload failed.")
            else:
                url=r.json()["upload_url"]
                tr = requests.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json={"audio_url":url}, headers=ASSEMBLYAI_HEADERS
                )
                if tr.status_code!=200:
                    st.error("Transcription request failed.")
                else:
                    tid=tr.json()["id"]
                    with st.spinner("Transcribing..."):
                        status="queued"
                        while status not in ["completed","error"]:
                            pr=requests.get(
                                f"https://api.assemblyai.com/v2/transcript/{tid}",
                                headers=ASSEMBLYAI_HEADERS
                            )
                            status=pr.json()["status"]
                            time.sleep(2)
                        if status=="completed":
                            text=pr.json()["text"]
                            st.write("Transcribed:",text)
                            keys=extract_possible_company_names(text)
                            st.write("Keywords:",keys)
                            symbols=set()
                            for kw in keys:
                                s=search_stock_symbol_fmp(kw)
                                if s=="RATE_LIMIT_EXCEEDED":
                                    break
                                if s:
                                    symbols.add(s)
                            if symbols:
                                st.write("Symbols:",",".join(symbols))
                                for sym in symbols:
                                    info=get_stock_summary(sym)
                                    if "error" in info:
                                        st.warning(info["error"])
                                    else:
                                        st.markdown(f"**{info['name']} ({sym})**")
                                        st.write(f"Price: ${info['price']}")
                                        st.write(f"Daily Δ: {info['daily_pct']}%  Weekly Δ: {info['weekly_pct']}%  Trend: {info['trend']}")
                            else:
                                st.warning("No valid symbols found.")
                        else:
                            st.error("Transcription error.")
    else:
        st.info("Upload or record audio to begin.")

# —— COLUMN 2: PDF Analysis ——
with col2:
    st.subheader("📄 PDF Document Analysis")
    pdf_file = st.file_uploader("Upload a finance PDF", type=["pdf"])
    if pdf_file:
        txt = extract_text_from_pdf(pdf_file)
        if txt:
            st.write(txt[:1000] + ("..." if len(txt)>1000 else ""))
            chunks = chunk_text(txt)
            st.write(f"Generated {len(chunks)} chunks.")
            for i, c in enumerate(chunks[:5]):
                st.markdown(f"**Chunk {i+1}:** {c[:200]}…")
        else:
            st.error("Failed to read PDF.")
