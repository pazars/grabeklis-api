# Run locally
Create a virtual environment in project directory:
```
python3 -m venv env
```
Activate the environment, set required environment variable, and run:
```
source ./env/bin/activate
export ENVIRONMENT=dev
fastapi dev main.py --port 8001
```
