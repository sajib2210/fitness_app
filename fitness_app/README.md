
# Fitness Flask App (Ready to Run)

Features:
- Set fitness goals (Fat Loss, Strength, Endurance, Push-ups, custom).
- Add workout records; choose to share with friends or community.
- View past workout records and see graphs (Chart.js).
- Add friends (connect) and share progress to friends/community feed.
- SQLite database (fitness.db) with sample users.

How to run:
```bash
python -m venv venv
source venv/bin/activate      # mac/linux
venv\Scripts\activate         # windows
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 in your browser.

Notes:
- This is a simple demo ready to be extended (authentication, file uploads, image hosting).
- Frontend uses Bootstrap and Chart.js via CDN; images are referenced from Unsplash.

Enjoy!
