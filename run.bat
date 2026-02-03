set VIRTUAL_ENV_DISABLE_PROMPT=
call .venv\Scripts\activate.bat
python main.py
call .venv\Scripts\deactivate.bat
@PAUSE