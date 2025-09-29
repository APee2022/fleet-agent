# Fleet Synthetic Data Agent

## Backend API
- Start the FastAPI service:
  ```bash
  uvicorn app.main:app --reload
  ```

## Streamlit UI
- Launch the Streamlit interface to craft prompts and download the generated CSVs:
  ```bash
  streamlit run app/ui/streamlit_app.py
  ```

Both the API and the UI write generated telemetry files to the `outputs/` directory by default.
