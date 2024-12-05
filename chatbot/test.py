import streamlit as st

# Define themes
themes = {
    "Light Theme": {
        "background_color": "#FFFFFF",
        "text_color": "#000000",
        "primary_color": "#4CAF50",
    },
    "Dark Theme": {
        "background_color": "#2E2E2E",
        "text_color": "#FFFFFF",
        "primary_color": "#FF5722",
    },
}

# Theme selector
selected_theme = st.sidebar.selectbox("Choose a theme", options=themes.keys())

# Apply styles
theme_colors = themes[selected_theme]
st.markdown(
    f"""
    <style>
    body {{
        background-color: {theme_colors['background_color']};
        color: {theme_colors['text_color']};
    }}
    .stButton>button {{
        background-color: {theme_colors['primary_color']};
        color: {theme_colors['text_color']};
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# Content
st.title("Dynamic Theme Example")
st.button("Click Me")
st.write(f"Current theme: {selected_theme}")
