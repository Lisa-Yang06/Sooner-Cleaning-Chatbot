import app as st
from query_openai import retrieve, answer

st.title("SoonerCleaning Chatbot")
query = st.text_input("Ask your question:")

if st.button("Send"):
    hits = retrieve(query, k=5)
    ans = answer(query, hits)
    st.write(ans)
    st.write("Sources:")
    for h in hits:
        st.write(f"[{h['rank']}] {h['title']} ({h['url']})")
