import streamlit as st
import requests
from urllib.parse import quote

st.set_page_config(page_title="Admin", page_icon="⚙️")
st.title("⚙️ Administration – Gestion des fichiers")

API_LIST_URL = "http://127.0.0.1:8000/admin/raw-files?recursive=false"
API_DELETE_URL = "http://127.0.0.1:8000/admin/raw-files"
API_UPLOAD_URL = "http://127.0.0.1:8000/admin/raw-files/upload-and-ingest"

# --- Section upload ---
st.subheader("⬆️ Ajouter un fichier")

uploaded_file = st.file_uploader("Sélectionner un fichier à uploader", type=None)
if uploaded_file:
    if st.button("Envoyer le fichier"):
        try:
            # On envoie le fichier à l'API FastAPI
            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
            response = requests.post(API_UPLOAD_URL, files=files)
            
            if response.status_code == 200:
                data = response.json()
                st.success(f"Fichier uploadé : {data.get('saved_as')} ({data.get('size_bytes')} bytes)")
            else:
                st.error(f"Erreur lors de l'upload : {response.status_code}")
                st.error(response.text)
        except Exception as e:
            st.error(f"Impossible d'uploader le fichier : {e}")

st.markdown("---")  # séparateur

# --- Section liste + suppression ---
st.subheader("📄 Fichiers existants")

try:
    response = requests.get(API_LIST_URL)
    response.raise_for_status()
    data = response.json()
    files = data.get("files", [])
except Exception as e:
    st.error(f"Impossible de récupérer les fichiers : {e}")
    files = []

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
            encoded_name = quote(rel_path)
            delete_url = f"{API_DELETE_URL}/{encoded_name}"

            try:
                del_resp = requests.delete(delete_url)
                if del_resp.status_code == 200:
                    st.success(f"Fichier supprimé : {filename}")
                else:
                    st.error(f"Erreur suppression : {del_resp.status_code}")
            except Exception as e:
                st.error(f"Impossible de supprimer le fichier : {e}")
