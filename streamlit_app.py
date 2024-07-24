import streamlit as st
import pandas as pd
import requests
import json

# Authentication function
def authenticate(username, password):
    return (username == st.secrets["login"]["username"] and 
            password == st.secrets["login"]["password"])

# OpenRouter API call
def analyze_ad_copy(ad_copy):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        },
        data=json.dumps({
            "model": "anthropic/claude-3.5-sonnet",
            "messages": [
                {"role": "system", "content": "You are an expert in analyzing Google Ads copy for ELISA kits. Provide a detailed analysis based on the given criteria."},
                {"role": "user", "content": f"Analyze the following Google Ads copy for ELISA kits:\n\n{ad_copy}\n\nProvide a comprehensive analysis including title analysis, snippet analysis, display URL analysis, ad extensions analysis, keyword relevance and density, call-to-action analysis, and overall ad strength evaluation. Format your response as a JSON object with keys for each analysis component."}
            ]
        })
    )
    return response.json()['choices'][0]['message']['content']

# Main application
def main():
    st.title("Google Ads ELISA Kit Analysis System")

    # Initialize session state for login
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # Login form
    if not st.session_state.logged_in:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if authenticate(username, password):
                st.session_state.logged_in = True
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")
        return

    # Main application (only accessible after login)
    uploaded_file = st.file_uploader("Upload your CSV file", type="csv")
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.write("Uploaded CSV file:")
        st.write(df)

        if st.button("Analyze Ads"):
            results = []
            for _, row in df.iterrows():
                ad_copy = f"Title: {row['Title']}\nSnippet: {row['Snippet']}\nDisplay URL: {row['Display URL']}\nExtensions: {row['Extensions']}"
                analysis = analyze_ad_copy(ad_copy)
                analysis_dict = json.loads(analysis)
                results.append(analysis_dict)

            results_df = pd.DataFrame(results)
            st.write("Analysis Results:")
            st.write(results_df)

            # Option to download results as CSV
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="ad_analysis_results.csv",
                mime="text/csv",
            )

    # Logout button
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.experimental_rerun()

if __name__ == "__main__":
    main()
