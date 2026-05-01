import streamlit as st
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.main import build_application
from app.schemas import QueryRequest


def main() -> None:
    st.set_page_config(page_title="Web3 AI System", layout="wide")
    st.title("Web3 AI System")
    st.caption("Hybrid architecture with separated insight and prediction engines.")

    app = build_application()

    with st.sidebar:
        asset = st.selectbox("Asset", ["BTC", "ETH", "SOL", "MATIC"], index=0)
        horizon_days = st.slider("Forecast horizon (days)", min_value=1, max_value=14, value=3)

    query = st.text_area(
        "Ask a market question",
        placeholder="Example: Predict ETH trend for the next 3 days and explain the current drivers.",
        height=120,
    )

    if st.button("Run analysis", type="primary") and query.strip():
        request = QueryRequest(user_query=query.strip(), asset=asset, horizon_days=horizon_days)
        try:
            response = app.handle_query(request)
        except Exception as exc:
            st.error(str(exc))
            st.info("Make sure dependencies are installed and OPENAI_API_KEY is configured.")
            return

        st.subheader(f"Route selected: {response.route}")

        if response.prediction:
            st.markdown("### Prediction")
            st.write(response.prediction)

        if response.explanation:
            st.markdown("### Explanation")
            st.write(response.explanation)

        st.markdown("### Final Output")
        st.write(response.final_output)

        if response.sources:
            st.markdown("**Retrieved context**")
            for source in response.sources:
                st.write(f"- {source}")

        if response.metadata:
            st.markdown("**Metadata**")
            st.json(response.metadata)


if __name__ == "__main__":
    main()
