# Setting up the project

```
#Create a folder then run 

mkdir Project && cd Project
git clone https://github.com/euginekoyo/WifiServer.git
cd wifiServer
```

```
touch .flaskenv
#add this line on it 
FLASK_APP=run.py
```
```
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv/Scripts/activate  # On Windows
pip install -r requirements.txt
```
### After that start the server
```
flask run
```
