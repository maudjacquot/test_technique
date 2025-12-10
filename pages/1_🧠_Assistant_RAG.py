import streamlit as st
import requests

API_URL = "http://localhost:8000/v1/chat/completions"

st.title("🧠 RAG Assistant – Streamlit")

question = st.text_input("Pose ta question :")

if st.button("Envoyer"):
    if question.strip():
        with st.spinner("Réflexion en cours..."):
            payload = {
                "user": "streamlit-user",
                "input": question
            }
            response = requests.post(API_URL, json=payload)

            if response.status_code == 200:
                data = response.json()
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
                st.error(f"Erreur API : {response.status_code}")
                st.error(response.text)
