from app import create_app, db, webui
from flask_migrate import Migrate

app = create_app()
app.secret_key = 'mvuTaCcyAk9RdESgzjwb'
Migrate(app, db)
webui.app = app
webui.start_threads()
