# Cytokine Effects Knowledge Base
Webpage: https://mpark20.github.io/cytokine-effects-kb/

Paper: In progress...


## Internal Setup Instructions
### Database setup
Run these commands to convert the CSV outputs to a PostgreSQL database (named "cytokines" by default).
```bash
python server/import_db.py --file path/to/data.csv
```

Note that if the table has already been created, it will not be changed. You may need to manually delete:
```
psql -U <username> postgres
DROP DATABASE cytokines 
```

### Start FastAPI server
```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000

# optionally, expose port for sharing and change API_BASE_URL to the url generated
ngrok http 8000
```