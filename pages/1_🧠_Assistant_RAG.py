import streamlit as st
from src.frontend.api_client import get_api_client

st.title("🧠 RAG Assistant – Streamlit")

# Récupérer le client API
api_client = get_api_client()

question = st.text_input("Pose ta question :")

if st.button("Envoyer"):
    if question.strip():
        with st.spinner("Réflexion en cours..."):
            # Appel API via le client sécurisé
            data = api_client.chat_completion(
                user="streamlit-user",
                question=question
            )

            if data:
                answer = data["choices"][0]["message"]["content"]

                st.write("### Réponse :")
                st.write(answer)

                usage = data.get("usage")
                if usage:
                    st.caption(
                        f"Tokens — prompt: {usage['prompt_tokens']} | "
                        f"réponse: {usage['completion_tokens']} | "
                        f"total: {usage['total_tokens']}"
                    )
    else:
        st.warning("⚠️ Pose une question d'abord !")