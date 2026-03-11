Bring up local webpage
'''
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
'''
Open: http://127.0.0.1:8000

### pre-commit linting
```
pip install pre-commit
pre-commit --version
pre-commit install
```
pre-commit installed at .git/hooks/pre-commit
