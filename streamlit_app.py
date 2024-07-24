import streamlit as st
import pandas as pd
import requests
import json
import time

# Set page config
st.set_page_config(page_title="Ad Analysis System", page_icon="📊", layout="wide")

# Authentication function
def authenticate(username, password):
    return (username == st.secrets["login_username"] and 
            password == st.secrets["login_password"])

# Function to check API rate limits
@st.cache_data(ttl=3600)
def check_rate_limits():
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {st.secrets['openrouter_api_key']}"},
        )
        if response.status_code == 200:
            data = response.json()['data']
            return data['rate_limit']['requests'], data['rate_limit']['interval']
        else:
            st.error("Failed to check rate limits. Please try again later.")
            return None, None
    except Exception as e:
        st.error(f"Error checking rate limits: {str(e)}")
        return None, None

# Function to analyze ad copy
def analyze_ad_copy(ad_copy, search_term):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter_api_key']}",
                "HTTP-Referer": "https://your-app-url.com",
                "X-Title": "Ad Copy Analysis App",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [
                    {"role": "system", "content": f"You are an expert in analyzing Google Ads copy for {search_term} products. Provide a concise, objective analysis based on the given criteria."},
                    {"role": "user", "content": f"""Analyze this Google Ad for {search_term} products:

Title: {ad_copy['title']}
Snippet: {ad_copy['snippet']}
Display URL: {ad_copy['displayed_link']}

Provide a brief analysis including:
1. Title effectiveness (score 1-10)
2. Snippet informativeness (score 1-10)
3. Overall ad strength (score 1-10)
4. Key strengths (comma-separated list)
5. Improvement suggestions (comma-separated list)

Format your response as a JSON object with these keys."""}
                ]
            }
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse API response as JSON"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}

# Function to process the dataframe
@st.cache_data
def process_dataframe(df, search_term, progress_bar, status_text):
    results = []
    total_rows = len(df)
    
    for index, row in df.iterrows():
        ad_copy = {
            'title': row['title'],
            'snippet': row['snippet'],
            'displayed_link': row['displayed_link']
        }
        analysis = analyze_ad_copy(ad_copy, search_term)
        
        result = {**ad_copy, **analysis}
        results.append(result)
        
        # Update progress
        progress = (index + 1) / total_rows
        progress_bar.progress(progress)
        status_text.text(f"Analyzed {index + 1} out of {total_rows} ads")
        
        # Respect rate limits
        time.sleep(1)  # Add a small delay between requests
    
    return pd.DataFrame(results)

# Main application
def main():
    st.title("Google Ads Analysis System")

    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'results' not in st.session_state:
        st.session_state.results = None

    # Login form
    if not st.session_state.logged_in:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if authenticate(username, password):
                    st.session_state.logged_in = True
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password")
        return

    # Main application (only accessible after login)
    uploaded_file = st.file_uploader("Upload your CSV file", type="csv")
    
    # Add input for search term
    search_term = st.text_input("Enter the search term you used to generate this data:", "")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.session_state.df = df
            st.write("Uploaded CSV file:")
            st.write(df)

            if search_term:
                if st.button("Analyze Ads"):
                    # Check rate limits
                    rate_limit, interval = check_rate_limits()
                    if rate_limit is None:
                        return

                    with st.spinner("Analyzing ads... This may take a few minutes."):
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        results_df = process_dataframe(df, search_term, progress_bar, status_text)
                        st.session_state.results = results_df

                    st.success(f"Analysis complete! Successfully analyzed {len(results_df)} ads.")

                # Display results if they exist in session state
                if st.session_state.results is not None:
                    st.subheader("Analysis Results:")
                    st.write(st.session_state.results)

                    # Option to download results as CSV
                    csv = st.session_state.results.to_csv(index=False)
                    st.download_button(
                        label="Download results as CSV",
                        data=csv,
                        file_name="ad_analysis_results.csv",
                        mime="text/csv",
                    )
            else:
                st.warning("Please enter the search term you used to generate this data.")
        except Exception as e:
            st.error(f"An error occurred while processing the file: {str(e)}")

    # Logout button
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

if __name__ == "__main__":
    main()
