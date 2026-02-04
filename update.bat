git fetch --all
git reset --hard HEAD
git pull
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt