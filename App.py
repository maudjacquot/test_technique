import streamlit as st

st.set_page_config(page_title="RAG App", page_icon="🤖", layout="centered")

st.title("🤖 Bienvenue dans ton application RAG")
st.markdown("## 🚀 Navigation rapide")

st.write("Choisis une section ci-dessous ou utilise le menu à gauche.")

# --- Boutons en colonnes ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🧠 Assistant RAG", use_container_width=True):
        st.switch_page("pages/1_🧠_Assistant_RAG.py")

with col2:
    if st.button("⚙️ Admin", use_container_width=True):
        st.switch_page("pages/2_⚙️_Admin.py")

st.markdown("---")

st.caption("Menu toujours disponible à gauche 👈 pour naviguer facilement.")
