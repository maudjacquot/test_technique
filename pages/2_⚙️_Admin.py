import streamlit as st
from src.frontend.api_client import get_api_client

st.set_page_config(page_title="Admin", page_icon="⚙️")
st.title("⚙️ Administration – Gestion des fichiers")

# Récupérer le client API
api_client = get_api_client()

# Initialiser les messages de session
if "upload_message" not in st.session_state:
    st.session_state.upload_message = None
if "delete_message" not in st.session_state:
    st.session_state.delete_message = None

# Afficher les messages s'ils existent
if st.session_state.upload_message:
    st.success(st.session_state.upload_message)
    st.session_state.upload_message = None  # Reset après affichage

if st.session_state.delete_message:
    st.error(st.session_state.delete_message)
    st.session_state.delete_message = None  # Reset après affichage

# --- Section upload ---
st.subheader("⬆️ Ajouter un fichier")

uploaded_file = st.file_uploader("Sélectionner un fichier à uploader", type=None)
if uploaded_file:
    if st.button("Envoyer le fichier"):
        with st.spinner("Upload en cours..."):
            data = api_client.upload_file(uploaded_file)
            
            if data:
                filename = data.get('saved_as')
                size = data.get('size_bytes')
                # Stocker le message dans session_state
                st.session_state.upload_message = f"✅ Fichier ajouté : **{filename}** ({size} bytes)"
                st.rerun()  # Rafraîchir la liste

st.markdown("---")

# --- Section liste + suppression ---
st.subheader("📄 Fichiers existants")

# Récupérer la liste des fichiers
data = api_client.list_files(recursive=False)

if data:
    files = data.get("files", [])
    
    if not files:
        st.info("Aucun fichier trouvé.")
    else:
        st.write("### Fichiers disponibles :")

        for f in files:
            filename = f.get("name", "Unknown")
            rel_path = f.get("rel_path", "")
            size = f.get("size_bytes", 0)

            col1, col2, col3 = st.columns([4, 1, 1])
            col1.write(filename)
            col2.write(f"{size} bytes")

            if col3.button("🗑️", key=f"del_{filename}"):
                with st.spinner(f"Suppression de {filename}..."):
                    result = api_client.delete_file(rel_path)
                    
                    if result:
                        # Stocker le message dans session_state
                        st.session_state.delete_message = f"🗑️ Fichier supprimé : **{filename}**"
                        st.rerun()  # Rafraîchir la liste
