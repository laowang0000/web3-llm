from pathlib import Path
import sys

from streamlit.web.cli import main as streamlit_main


if __name__ == "__main__":
    script_path = Path(__file__).resolve().parent / "app" / "frontend" / "streamlit_app.py"
    sys.argv = ["streamlit", "run", str(script_path)]
    raise SystemExit(streamlit_main())
