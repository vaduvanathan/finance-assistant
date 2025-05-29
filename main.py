import streamlit as st
import requests
import time
import yfinance as yf
import string
import fitz
import io # Required for handling audio bytes in memory
import base64 # Required by streamlit_audiorecorder
from streamlit_audiorecorder import st_audiorecorder # Import the audio recorder

st.set_page_config(page_title="Finance Voice & Document Assistant", layout="wide")
st.title("🎙️ Multi-Source Finance Assistant")

# API keys
ASSEMBLYAI_API_KEY = "a5c865ecb6cd4152ad9c91564a753cd2"
# Note: FMP free tier is very limited. You might hit limits quickly.
FMP_API_KEY = "vLJtmE98fFBnb8zw65y0Sl9yJjmB2u9Q"
headers = {"authorization": ASSEMBLYAI_API_KEY}

# --- Functions ---

# 🔍 Clean keywords for symbol search
def extract_possible_company_names(text):
    # Remove all punctuation from the text before splitting
    text_without_punctuation = text.translate(str.maketrans('', '', string.punctuation))
    words = text_without_punctuation.split()

    # --- UPDATED STOPWORDS LIST ---
    stopwords = {
        "the", "what", "about", "is", "stock", "market", "price", "update",
        "how", "in", "to", "and", "of", "a", "an", "can", "you", "give", "me",
        "tell", "show", "today", "quote", "value", "exchange", "it", "doing",
        "for", "report", "news", "brief", "summary", "daily", "weekly", "change",
        "percent", "at", "on", "up", "down", "high", "low", "open", "close", "last",
        "morning", "afternoon", "evening", "today's", "yesterday's", "current",
        "companies", "company", "shares", "indices", "index", "group", "holdings",
        "performance", "analysis", "latest", "find", "out", "about", "looking",
        "for", "which", "are", "these", "those", "any", "some", "get", "inform",
        "us", "please","today", "tomorrow", "yesterday",
        "can you tell me", "can you give me", "can you find",
        "what about", "how about", "what's the", "tell me about"
    }
    # --- END OF UPDATED STOPWORDS LIST ---

    # Filter out stopwords and very short words (length > 2)
    # Convert words to lowercase for stopword comparison
    return [w for w in words if w.lower() not in stopwords and len(w) > 2]

# 🔎 Search symbol via FMP
def search_stock_symbol_fmp(keyword):
    try:
        # FMP free tier has very tight limits.
        # This endpoint specifically for search-name might also have limits.
        url = f"https://financialmodelingprep.com/api/v3/search?query={keyword}&limit=1&apikey={FMP_API_KEY}"
        res = requests.get(url)
        if res.status_code == 200:
            results = res.json()
            if results:
                # Prioritize common stock types if multiple results, otherwise just take the first
                for r in results:
                    if r.get("exchangeShortName") in ["NASDAQ", "NYSE", "BSE", "NSE", "HKEX", "TSE", "SSE"]: # Added more exchanges
                        return r["symbol"]
                return results[0]["symbol"] # Fallback to first if no preferred exchange
        elif res.status_code == 429:
            st.error("❌ FMP API Rate Limit Exceeded. Please wait a moment and try again, or check your API key.")
            return None
        else:
            print(f"FMP search error status: {res.status_code}, response: {res.text}")
    except Exception as e:
        print(f"Symbol search error for '{keyword}': {e}")
    return None

# 📈 Get stock data with daily/weekly change
def get_stock_summary(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info

        # Check if info is empty or doesn't contain basic price data
        if not info or not info.get("regularMarketPrice") and not info.get("currentPrice"):
             return {"error": f"No valid data found for symbol: {symbol}. It might be an invalid ticker or no data available."}

        # Get historical data for last 7 days
        hist = stock.history(period="7d")
        if hist.empty:
            # If no 7d history, try 5d or 1d to at least get a current price
            hist = stock.history(period="5d")
            if hist.empty:
                hist = stock.history(period="1d")
                if hist.empty:
                    return {"error": f"No historical data available for {symbol}."}

        # Assuming current_price is the last available price from info, or hist if info fails
        current_price = info.get("currentPrice", info.get("regularMarketPrice", hist["Close"].iloc[-1]))

        # Get the previous day's closing price from historical data for daily change
        previous_close_hist = 0
        if len(hist) >= 2:
            previous_close_hist = hist["Close"].iloc[-2]
        elif len(hist) == 1: # If only one day of history, previousClose might be in info
            previous_close_hist = info.get("previousClose", 0)
        else:
            previous_close_hist = info.get("previousClose", 0) # Fallback if no history

        daily_change_pct = ((current_price - previous_close_hist) / previous_close_hist) * 100 if previous_close_hist else 0

        # Calculate 7-day % change
        week_ago_price = hist["Close"].iloc[0] # This is the oldest price in the relevant history
        weekly_change_pct = ((current_price - week_ago_price) / week_ago_price) * 100 if week_ago_price else 0

        # Trend summary
        trend = "up 📈" if weekly_change_pct > 0 else "down 📉" if weekly_change_pct < 0 else "unchanged"

        return {
            "name": info.get("longName", symbol), # Use symbol if longName not found
            "symbol": symbol, # Include symbol for clarity
            "price": current_price,
            "open": info.get("open", "N/A"),
            "high": info.get("dayHigh", "N/A"),
            "low": info.get("dayLow", "N/A"),
            "marketCap": info.get("marketCap", "N/A"),
            "summary": info.get("longBusinessSummary", "No business summary available."),
            "daily_change_pct": round(daily_change_pct, 2),
            "weekly_change_pct": round(weekly_change_pct, 2),
            "trend": trend
        }
    except Exception as e:
        return {"error": str(e)}

# Function to extract text from PDF (using PyMuPDF)
def extract_text_from_pdf(file):
    text = ""
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        st.error(f"❌ Error reading PDF: {e}")
        return None
    return text

# NEW FUNCTION: Chunking text for RAG
# Line 106: Start of new function `chunk_text`
def chunk_text(text, chunk_size=300, chunk_overlap=50):
    """Splits text into chunks of a specified size with overlap."""
    tokens = text.split()  # Simple tokenization by spaces
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk = " ".join(tokens[start:end])
        chunks.append(chunk)
        start += chunk_size - chunk_overlap
    return chunks
# Line 116: End of new function `chunk_text`


# --- Streamlit UI and Logic ---

# Use columns for a cleaner layout of the two main features
col1, col2 = st.columns(2)

with col1:
    st.subheader("🎤 Voice Query Analysis")
    # Line 123: Replace file uploader with audio recorder
    # audio_file = st.file_uploader("Upload an MP3 file for voice query", type=["mp3"])
    wav_audio_data = st_audiorecorder() # Microphone input widget

    if wav_audio_data is not None: # Check if audio data is available from the recorder
        # Use a unique key for the button to avoid issues if other buttons exist
        if st.button("Transcribe & Fetch Stock (Voice)", key="transcribe_button"):
            # Line 129: Changed from audio_file to wav_audio_data
            with st.spinner("Uploading audio to AssemblyAI..."):
                # AssemblyAI's upload endpoint can take raw bytes
                # We need to provide a filename and content type
                files = {"file": ("audio.wav", wav_audio_data, "audio/wav")}
                upload_res = requests.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers=headers,
                    files=files # Use the files dictionary with bytes
                )
                if upload_res.status_code != 200:
                    st.error("❌ Audio upload failed to AssemblyAI.")
                    st.write(upload_res.text)
                else:
                    audio_url = upload_res.json()["upload_url"]

                    with st.spinner("Sending for transcription..."):
                        json_data = {"audio_url": audio_url}
                        transcript_res = requests.post(
                            "https://api.assemblyai.com/v2/transcript",
                            json=json_data,
                            headers=headers
                        )

                        if transcript_res.status_code != 200:
                            st.error("❌ Transcription request failed.")
                            st.write(transcript_res.text)
                        else:
                            transcript_id = transcript_res.json()["id"]

                            with st.spinner("Transcribing audio (this may take a moment)..."):
                                status = "queued"
                                while status not in ["completed", "error"]:
                                    polling_res = requests.get(
                                        f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                                        headers=headers
                                    )
                                    status = polling_res.json()["status"]
                                    time.sleep(3) # Wait before polling again

                                if status == "completed":
                                    transcribed_text = polling_res.json()["text"]
                                    st.success("✅ Voice Transcription Complete:")
                                    st.write(transcribed_text)

                                    keywords = extract_possible_company_names(transcribed_text)
                                    st.write("🔍 Extracted keywords from voice:", keywords)

                                    found_symbols = set() # Use a set to avoid duplicate symbols

                                    # Try to find symbols using FMP (prioritized for broader search)
                                    for keyword in keywords:
                                        symbol = search_stock_symbol_fmp(keyword)
                                        if symbol:
                                            found_symbols.add(symbol)

                                    # Also, try to directly validate keywords as YFinance tickers
                                    for word in keywords:
                                        cleaned_word = word.upper()
                                        if cleaned_word not in found_symbols and (len(cleaned_word) <= 5 and cleaned_word.isalpha() or '.' in cleaned_word):
                                            try:
                                                ticker_info = yf.Ticker(cleaned_word).info
                                                if ticker_info and ticker_info.get("symbol") == cleaned_word and ticker_info.get("regularMarketPrice"):
                                                    found_symbols.add(cleaned_word)
                                            except:
                                                pass

                                    if found_symbols:
                                        st.info(f"🔎 Found potential stock symbols: {', '.join(list(found_symbols))}")

                                        all_stock_summaries = [] # To store summaries of all found stocks
                                        for symbol in list(found_symbols): # Convert set to list to iterate
                                            data = get_stock_summary(symbol)
                                            if "error" not in data:
                                                all_stock_summaries.append(data)
                                            else:
                                                st.warning(f"⚠️ {data['error']}")

                                        if all_stock_summaries:
                                            st.subheader("📊 Stock Information from Voice Query:")
                                            for data in all_stock_summaries:
                                                st.markdown("---") # Separator for each stock
                                                st.write(f"**{data['name']} ({data['symbol']})**")
                                                st.write(f"💰 Current Price: ${data['price']:.2f}")
                                                if data['open'] != 'N/A': # Check if data is available
                                                    st.write(f"📈 Open: ${data['open']:.2f}, High: ${data['high']:.2f}, Low: ${data['low']:.2f}")
                                                if data['marketCap'] != 'N/A':
                                                    st.write(f"🏢 Market Cap: {data['marketCap']}")
                                                st.write(f"📊 Daily Change: **{data['daily_change_pct']:.2f}%**")
                                                st.write(f"📅 Weekly Change: **{data['weekly_change_pct']:.2f}%**")
                                                st.write(f"📈 Weekly Trend: {data['trend']}")

                                                # Insight sentence for weekly change
                                                if data['weekly_change_pct'] > 0:
                                                    insight_sentence = f"{data['name']} stocks are up by {data['weekly_change_pct']:.2f}% this week."
                                                elif data['weekly_change_pct'] < 0:
                                                    insight_sentence = f"{data['name']} stocks are down by {abs(data['weekly_change_pct']):.2f}% this week."
                                                else:
                                                    insight_sentence = f"{data['name']} stocks are unchanged this week."
                                                st.info(f"💡 Insight: {insight_sentence}") # Display the insight sentence

                                                if data['summary'] and data['summary'] != 'No business summary available.':
                                                    st.markdown(f"📝 **Business Summary:** {data['summary'][:300]}...") # Show a snippet of summary
                                        else:
                                            st.warning("⚠️ No detailed stock data could be retrieved for the identified symbols.")
                                    else:
                                        st.warning("⚠️ No valid stock symbols or company names found in your voice input.")
                                else:
                                    st.error("❌ Voice Transcription failed.")
                                    st.write(polling_res.json())
    elif wav_audio_data is None:
        st.info("Please click the microphone and record your query.")


with col2:
    st.subheader("📄 PDF Document Analysis")
    pdf_file = st.file_uploader("Upload a Finance PDF for analysis", type=["pdf"])

    if pdf_file:
        st.info("✅ PDF uploaded successfully")
        extracted_text = extract_text_from_pdf(pdf_file)

        if extracted_text:
            st.subheader("📑 Extracted Text from PDF Preview:")
            # Show a longer preview but with ellipsis if truncated
            st.write(extracted_text[:4000] + "..." if len(extracted_text) > 4000 else extracted_text)

            # Line 323: Start of Chunking Implementation
            st.subheader("✂️ PDF Text Chunks:")
            chunks = chunk_text(extracted_text)
            if chunks:
                st.info(f"Generated {len(chunks)} chunks from the PDF text.")
                for i, chunk in enumerate(chunks[:5]):  # Display the first 5 chunks
                    st.markdown(f"**Chunk {i+1}:**")
                    st.write(chunk[:500] + "..." if len(chunk) > 500 else chunk)
                    st.markdown("---")
                if len(chunks) > 5:
                    st.warning("Displaying only the first 5 chunks for preview.")
            else:
                st.warning("No chunks were generated from the PDF text.")
            # Line 337: End of Chunking Implementation

            st.subheader("💡 Further Analysis of PDF Content:")
            st.write("You can implement more advanced analysis of the extracted text here. For example:")
            st.markdown("- **Identify key entities (companies, dates, financial figures)**")
            st.markdown("- **Summarize sections**")
            st.markdown("- **Answer questions based on PDF content (RAG)**")

            # Example: Simple keyword search in PDF
            st.markdown("**Simple Keyword Search:**")
            pdf_keywords_to_find = ["earnings", "revenue", "profit", "loss", "outlook", "guidance", "dividend", "acquisition", "merger"]
            pdf_text_lower = extracted_text.lower() # Convert once for efficiency
            found_pdf_keywords = [kw for kw in pdf_keywords_to_find if kw in pdf_text_lower]
            if found_pdf_keywords:
                st.info(f"Found financial keywords in the PDF: {', '.join(found_pdf_keywords)}")
            else:
                st.write("No specific financial keywords found in the preview.")

            # Example: Try to find stock symbols in the PDF content itself
            st.markdown("**Attempting to find stock symbols in PDF:**")
            pdf_found_symbols = set()

            # Extract possible company names from the PDF text using the same logic
            pdf_possible_names = extract_possible_company_names(extracted_text)

            # Try to find symbols using FMP for keywords from PDF
            for keyword in pdf_possible_names:
                symbol = search_stock_symbol_fmp(keyword)
                if symbol:
                    pdf_found_symbols.add(symbol)

            # Also, try to directly validate keywords from PDF as YFinance tickers
            for word in pdf_possible_names: # Re-use cleaned words
                cleaned_word = word.upper()
                if cleaned_word not in pdf_found_symbols and (len(cleaned_word) <= 5 and cleaned_word.isalpha() or '.' in cleaned_word):
                    try:
                        ticker_info = yf.Ticker(cleaned_word).info
                        if ticker_info and ticker_info.get("symbol") == cleaned_word and ticker_info.get("regularMarketPrice"):
                            pdf_found_symbols.add(cleaned_word)
                    except:
                        pass

            if pdf_found_symbols:
                st.info(f"🔎 Found potential stock symbols in PDF: {', '.join(list(pdf_found_symbols))}")
                st.subheader("📊 Stock Information from PDF (if found):")
                pdf_stock_data_results = {}
                for symbol in list(pdf_found_symbols):
                    data = get_stock_summary(symbol)
                    if "error" not in data:
                        pdf_stock_data_results[symbol] = data
                    else:
                        st.warning(f"⚠️ {data['error']} for symbol from PDF: {symbol}")

                if pdf_stock_data_results:
                    for symbol, data in pdf_stock_data_results.items():
                        st.markdown("---") # Separator for each stock
                        st.write(f"**{data['name']} ({symbol})**")
                        st.write(f"💰 Current Price: ${data['price']:.2f}")
                        if data['summary'] and data['summary'] != 'No business summary available.':
                            st.markdown(f"📝 **Business Summary:** {data['summary'][:200]}...")
                else:
                    st.write("Could not retrieve valid stock data for symbols found in PDF.")
            else:
                st.write("No stock symbols or company names found in the PDF content that could be automatically identified.")


st.sidebar.markdown("---")
st.sidebar.markdown("## Project Information")
st.sidebar.markdown("This is a multi-source finance assistant prototype.")
st.sidebar.markdown("It processes voice queries via **AssemblyAI** and fetches real-time stock data via **`yfinance`** and **FMP API**.")
st.sidebar.markdown("It also extracts text from uploaded PDF documents using **`PyMuPDF`** for analysis and attempts to find stock symbols within them.")
st.sidebar.markdown("---")
st.sidebar.markdown("### Key Features:")
st.sidebar.markdown("- **Voice-to-Text**: Transcribes spoken queries.")
st.sidebar.markdown("- **Intelligent Stock Search**: Identifies company names/tickers from voice or text.")
st.sidebar.markdown("- **Multi-Stock Info**: Fetches and displays data for multiple identified stocks.")
st.sidebar.markdown("- **Daily/Weekly Change**: Calculates and displays percentage changes.")
st.sidebar.markdown("- **PDF Text Extraction**: Extracts and previews text from finance PDFs.")
st.sidebar.markdown("- **PDF Stock Identification**: Attempts to find stock symbols within PDF content.")
st.sidebar.markdown("- **PDF Text Chunking**: Breaks down PDF text into manageable chunks for RAG.")
st.sidebar.markdown("---")
st.sidebar.markdown("### Dependencies:")
st.sidebar.markdown("- `streamlit`")
st.sidebar.markdown("- `requests`")
st.sidebar.markdown("- `yfinance`")
st.sidebar.markdown("- `PyMuPDF` (installed as `fitz`)")
st.sidebar.markdown("- `streamlit_audiorecorder` (for microphone input)")
