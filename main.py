import streamlit as st
import requests
import time
import yfinance as yf
import string # Import the string module for punctuation

# import pyttsx3 # Commented out for Replit/Streamlit Cloud compatibility

st.set_page_config(page_title="Finance Voice Assistant")
st.title("🎙️ Voice Finance Assistant")

# API keys
ASSEMBLYAI_API_KEY = "a5c865ecb6cd4152ad9c91564a753cd2"
# Note: FMP free tier is very limited. You might hit limits quickly.
FMP_API_KEY = "vLJtmE98fFBnb8zw65y0Sl9yJjmB2u9Q"
headers = {"authorization": ASSEMBLYAI_API_KEY}

# Initialize the TTS engine (Commented out)
# engine = pyttsx3.init()

# Upload audio file
audio_file = st.file_uploader("Upload an MP3 file", type=["mp3"])

# 🔍 Clean keywords for symbol search
def extract_possible_company_names(text):
    # Remove all punctuation from the text before splitting
    # This also handles cases like "Apple?" and "TSLA!"
    text_without_punctuation = text.translate(str.maketrans('', '', string.punctuation))
    words = text_without_punctuation.split()

    # --- UPDATED STOPWORDS LIST AS PROVIDED BY YOU ---
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
        "us", "please","today", "tomorrow", "yesterday", # Changed "today?" to "today" as punctuation is removed
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
                    if r.get("exchangeShortName") in ["NASDAQ", "NYSE", "BSE", "NSE", "HKEX"]: # Add relevant exchanges
                        return r["symbol"]
                return results[0]["symbol"] # Fallback to first if no preferred exchange
    except Exception as e:
        print(f"Symbol search error for '{keyword}': {e}")
    return None

# 📈 Get stock data with daily/weekly change
def get_stock_summary(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info

        # Get historical data for last 7 days
        # yfinance period="7d" fetches enough data for the last 7 trading days.
        hist = stock.history(period="7d")
        if hist.empty:
            return {"error": "No historical data available for " + symbol}

        # Assuming current_price is the last available price from info, or hist if info fails
        current_price = info.get("currentPrice", hist["Close"].iloc[-1])

        # Get the previous day's closing price from historical data for daily change
        if len(hist) >= 2:
            previous_close_hist = hist["Close"].iloc[-2]
        else:
            previous_close_hist = info.get("previousClose", 0) # Fallback if only 1 day of hist data


        daily_change_pct = ((current_price - previous_close_hist) / previous_close_hist) * 100 if previous_close_hist else 0

        # Calculate 7-day % change
        week_ago_price = hist["Close"].iloc[0] # This is the oldest price in the 7d history

        weekly_change_pct = ((current_price - week_ago_price) / week_ago_price) * 100 if week_ago_price else 0

        # Trend summary
        trend = "up 📈" if weekly_change_pct > 0 else "down 📉" if weekly_change_pct < 0 else "unchanged"

        return {
            "name": info.get("longName", "N/A"),
            "symbol": symbol, # Include symbol for clarity
            "price": current_price,
            "open": info.get("open", "N/A"),
            "high": info.get("dayHigh", "N/A"),
            "low": info.get("dayLow", "N/A"),
            "marketCap": info.get("marketCap", "N/A"),
            "summary": info.get("longBusinessSummary", "N/A"),
            "daily_change_pct": round(daily_change_pct, 2),
            "weekly_change_pct": round(weekly_change_pct, 2),
            "trend": trend
        }
    except Exception as e:
        return {"error": str(e)}

# Function to speak text (Commented out)
# def speak(text):
#     engine.say(text)
#     engine.runAndWait()

# Main process
if audio_file and st.button("Transcribe & Fetch Stock"):
    with st.spinner("Uploading audio..."):
        upload_res = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            files={"file": audio_file}
        )
        if upload_res.status_code != 200:
            st.error("❌ Upload failed.")
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

                    with st.spinner("Transcribing..."):
                        status = "queued"
                        while status not in ["completed", "error"]:
                            polling_res = requests.get(
                                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                                headers=headers
                            )
                            status = polling_res.json()["status"]
                            time.sleep(3)

                        if status == "completed":
                            transcribed_text = polling_res.json()["text"]
                            st.success("✅ Transcription Complete:")
                            st.write(transcribed_text)
                            # speak(f"Transcription complete. You said: {transcribed_text}") # Commented out

                            keywords = extract_possible_company_names(transcribed_text)
                            st.write("🔍 Keywords extracted:", keywords)

                            found_symbols = set() # Use a set to avoid duplicate symbols
                            for keyword in keywords:
                                symbol = search_stock_symbol_fmp(keyword)
                                if symbol:
                                    found_symbols.add(symbol)

                            # Also check if any extracted keyword is a direct, valid ticker
                            for word in keywords:
                                # Ensure word is clean before trying as ticker
                                cleaned_word = word.upper()
                                try:
                                    # Attempt to get info to validate if it's a ticker
                                    ticker_info = yf.Ticker(cleaned_word).info
                                    # Check if yfinance confirms it's a valid ticker and it matches the cleaned word
                                    if ticker_info and ticker_info.get("symbol") == cleaned_word:
                                        found_symbols.add(cleaned_word)
                                except:
                                    pass # Not a direct ticker, ignore

                            if found_symbols:
                                st.info(f"🔎 Found potential stock symbols: {', '.join(list(found_symbols))}")

                                all_stock_summaries = [] # To store summaries of all found stocks
                                for symbol in list(found_symbols): # Convert set to list to iterate
                                    data = get_stock_summary(symbol)
                                    if "error" not in data:
                                        all_stock_summaries.append(data)
                                    else:
                                        st.warning(f"⚠️ Could not retrieve detailed data for {symbol}: {data['error']}")

                                if all_stock_summaries:
                                    st.subheader("📊 Stock Information:")
                                    # summary_speech_text = "Here's a brief overview of the stocks mentioned: " # For TTS
                                    for data in all_stock_summaries:
                                        st.write(f"---")
                                        st.write(f"**{data['name']} ({data['symbol']})**")
                                        st.write(f"💰 Current Price: ${data['price']:.2f}")
                                        st.write(f"📈 Open: ${data['open']:.2f}, High: ${data['high']:.2f}, Low: ${data['low']:.2f}")
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
                                        st.write(f"💡 Insight: {insight_sentence}") # Display the insight sentence

                                        st.markdown(f"📝 {data['summary']}")
                                        # summary_speech_text += f"{data['name']} currently trading at ${data['price']:.2f}. " # For TTS
                                        # summary_speech_text += f"Daily change: {data['daily_change_pct']:.2f} percent. " # For TTS
                                        # summary_speech_text += f"Weekly trend is {data['trend']}. " # For TTS
                                        # summary_speech_text += f"Insight: {insight_sentence}. " # Add insight to speech text if enabled

                                    # speak(summary_speech_text) # Commented out
                                else:
                                    st.warning("⚠️ No detailed stock data could be retrieved for the identified symbols.")
                                    # speak("No detailed stock data could be retrieved for the identified symbols.") # Commented out
                            else:
                                st.warning("⚠️ No valid stock symbols or company names found in your voice input.")
                                # speak("No valid stock symbols or company names found in your voice input.") # Commented out
                        else:
                            st.error("❌ Transcription failed.")
                            st.write(polling_res.json())
                            # speak("Transcription failed.") # Commented out