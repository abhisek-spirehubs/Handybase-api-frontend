# Handybase API — Quick start

A minimal set of instructions to run this FastAPI-based project locally after cloning from Git.

Requirements
- Python 3.10+ (3.11 recommended)
- Git
- MongoDB (running/local or remote)


Quick setup 

0. Clone the repo

```bash
git clone <repo-url>
cd Handybase
```

1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

window - .\.venv\Scripts\Activate.ps1 

2. Install dependencies

```bash
pip install -r requirements.txt
```

###admin create-
python3 -m app.scripts.init_admin create admin@handybase.com mypassword123 "System Admin"


3. Provide environment variables

The project uses `pydantic-settings` and reads `.env` from the project root. Create a `.env` file with at least the required variables:

```bash
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=handybase_db
JWT_SECRET=your_jwt_secret_here
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=smtp_user
SMTP_PASSWORD=smtp_password
SMTP_FROM="noreply@example.com"
# Optional / defaults:
# ENV=local
# DEBUG=True
```

See `app/core/config.py` for all configurable environment variables and defaults.

4. Ensure MongoDB is running

For local development you can start a MongoDB container or install it on your machine. Redis is no longer required by this project; rate limiting is handled in‑memory by the application itself so you can ignore any `REDIS_URL` variables.
```

5. Start the app as usual (with venv active):

```bash
python -m uvicorn app.main:app --reload
```

6. Test the rate limiter by calling a rate-limited endpoint (login is limited to 5 attempts / 60s):

```bash
for i in {1..6}; do
	http_code=$(curl -s -o /dev/null -w "%{http_code}" \
		-X POST http://localhost:8000/api/v1/auth/login \
		-H "Content-Type: application/json" \
		-d '{"email":"no@one@example.com","password":"x"}')
	echo "Attempt $i -> HTTP $http_code"
done
```

The 6th request should return 429 if the in‑memory rate limiter is working.

6. Run the application

Start the server with uvicorn (the same entry used by the project):

```bash
python -m uvicorn app.main:app --reload
# or the explicit form used in `app/main.py`:
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit the interactive API docs at: `http://localhost:8000/docs`

7. (Optional) Create initial admin user

The repo includes a script to create a seed/admin user: `app/scripts/init_admin.py`.

Usage:

```bash
# Example: create an admin
python -m app.scripts.init_admin create admin@example.com strongpassword "Admin Name"
```

WebSocket (chat) usage

- The project's WebSocket chat endpoint is mounted under the API prefix. With the default API prefix (`/api/v1`) the full WebSocket path is:

```
ws://localhost:8000/api/v1/ws/chat/{booking_id}?token=<JWT_TOKEN>
```

- Notes:
	- The connection expects a `token` query parameter containing a valid access JWT. The token is validated by `app/dependencies/websocket_auth.py` (it extracts `token` from `websocket.query_params`).
	- The WebSocket route uses an in-memory `ConnectionManager` (`app/core/socket_manager.py`) to track active sockets. This works for single-process development. For multi-worker or multi-instance deployments you will need a centralized pub/sub (e.g., Redis) to relay messages between workers (not implemented here).


Notes & troubleshooting
- The app expects `MONGO_URI` and other required secrets to be present; missing required env vars will cause startup errors from pydantic.
- If the rate limiter fails, verify the application has write/read access to its memory (this is rarely an issue). Redis is not required.
- Media files are served from the `media/` directory (created automatically by the app). Ensure the process has write permission.
- Logs are written to the path configured by `LOG_FILE_PATH` (default `logs/app.log`) — ensure the `logs/` directory exists and is writable.



ws://localhost:8000/api/v1/ws/chat/699d95ded6e2a0b1507c221a?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OTlkOTMyZWQ2ZTJhMGIxNTA3YzIyMTYiLCJyb2xlIjoiY2xpZW50IiwiZXhwIjoxNzcyMDAzOTgzfQ.l9MnWAz2MzeJPM6Ft79XrNkg_BRzY_tgyXtNuUgwk8U




sushil@Abhisek-HP-Compaq-Pro-6300-SFF:~/Documents/HANDYBASE_API _frontend/handy-base-api$ cd frontend/
sushil@Abhisek-HP-Compaq-Pro-6300-SFF:~/Documents/HANDYBASE_API _frontend/handy-base-api/frontend$ source venv/bin/activate
(venv) sushil@Abhisek-HP-Compaq-Pro-6300-SFF:~/Documents/HANDYBASE_API _frontend/handy-base-api/frontend$ FASTAPI_BASE_URL=http://localhost:8000/api/v1 python manage.py runserver 8080




sushil@Abhisek-HP-Compaq-Pro-6300-SFF:~/Documents/HANDYBASE_API _frontend/handy-base-api$ source .venv/bin/activate
(.venv) sushil@Abhisek-HP-Compaq-Pro-6300-SFF:~/Documents/HANDYBASE_API _frontend/handy-base-api$ uvicorn app.main:app --reload







Root: /home/sushil/Documents/HANDYBASE_API _frontend/handy-base-api

.env
.env.example
.codex
.python-version
.venv/ (virtualenv — large; site-packages omitted below)
bin/
lib/
...
.vscode/
extensions.json
firebase-messaging-sw.js
handybase-74eb1-firebase-adminsdk-fbsvc-9b2b82dab4.json
logs/
app.log
media/
avatars/
91554ba948eb4651b88b59e85bca61d8.jpg
e284d2e8aa1644649b1b6461a3988a2d.jpg
providers/
profile/
bc59b48131324c36be8ba3e02f0e9d74.jpg
progress.md
readme.md
subscription_plans_json.txt
test_notifications.html
app/

pycache/
main.cpython-312.pyc
api/
v1/
endpoints/
admin.py
analytics.py
announcement.py
availability.py
booking.py
category.py
chat_message.py
document_exchange.py
fcm.py
financial_report.py
health.py
invoice.py
job_request.py
notification.py
plan.py
provider.py
review.py
service.py
support_ticket.py
subscription.py
video_portfolio.py
client.py
client_review.py
client_features.py
pycache/
many .pyc files for endpoints
pycache/
router.cpython-312.pyc
router.py
__init__.py (implied)
sockets/
chat_socket.py
pycache/
background_task.py
core/
__init__.py
pycache/
config.cpython-312.pyc
handlers.cpython-312.pyc
exceptions.cpython-312.pyc
redis_client.cpython-312.pyc
database.cpython-312.pyc
security.cpython-312.pyc
socket_manager.cpython-312.pyc
firebase.cpython-312.pyc
config.py
database.py
exceptions.py
firebase.py
handlers.py
redis_client.py
security.py
socket_manager.py
dependencies/
auth.py
rate_limit.py
subscription.py
websocket_auth.py
pycache/
middleware/
__init__.py
logging.py
pycache/
models/
pycache/
announcement.py
booking.py
category.py
chat_message.py
chat_room.py
client_plan.py
client_review.py
client_subscription.py
common.py
fcm_token.py
invoice.py
job_request.py
notification.py
plan.py
provider_analytics.py
provider_availability.py
provider_plan.py
provider_subscription.py
provider.py
quotation.py
review.py
service.py
subscription.py
support_ticket.py
user.py
schemas/
pycache/
admin.py
analytics.py
announcement.py
auth.py
availability.py
base.py
booking.py
category.py
chat_message.py
client.py
client_features.py
client_rating.py
common.py
fcm.py
financial_report.py
invoice.py
job_request.py
notification.py
pagination.py
plan.py
provider.py
review.py
service.py
subscription.py
support_ticket.py
video_portfolio.py
scripts/
backfill_trends.py
init_admin.py
pycache/
services/
pycache/
admin_service.py
analytics_service.py
announcement_service.py
auth_service.py
availability_service.py
booking_service.py
category_service.py
chat_service.py
client_review.py
client_service.py
fcm_service.py
financial_report.py
invoice_service.py
job_request.py
notification_orchestrator.py
notification_service.py
plan_service.py
provider_service.py
provider_subscription_service.py (or similar)
provider_availability_service.py (or similar)
review_service.py
service_service.py
support_ticket.py
subscription_service.py
video_portfolio.py
... (many service modules and compiled .pyc files)
utils/
pycache/
email.py
file_upload.py
logger.py
pdf_generator.py
cache.py (if present)
main.py
templates/
email-template.html
subscription-expiring.html
subscription-expired.html
frontend/

manage.py
apps/
authentication/
templates/
authentication/
login.html
register_client.html
register_provider.html
forgot_password.html
verify_otp.html
reset_password.html
pending_approval.html
views.py
urls.py
apps.py
pycache/
core/
apps.py
api_client.py
pycache/
dashboard/
views.py
urls.py (if present)
templates/
dashboard/
admin_clients.html
admin_categories.html
admin_approvals.html
pycache/
service/
views.py
urls.py?
templates/
service/
create.html
edit.html
... (other Django apps present under apps/ — e.g., availability, chat, etc., depending on repo)
config/
__init__.py
asgi.py
wsgi.py
urls.py
settings/
base.py
local.py
pycache/
dependencies/
auth.py
rate_limit.py
subscription.py
websocket_auth.py
middleware/
logging.py
__init__.py
models/ (Django-facing models or API translation models)
announcement.py
booking.py
category.py
chat_message.py
chat_room.py
client_plan.py
client_review.py
client_subscription.py
common.py
fcm_token.py
invoice.py
job_request.py
notification.py
plan.py
provider_analytics.py
provider_availability.py
provider_plan.py
provider_subscription.py
provider.py
quotation.py
review.py
service.py
subscription.py
support_ticket.py
user.py
pycache/
schemas/
many serializer-like modules (admin.py, auth.py, client.py, service.py, etc.)
scripts/
backfill_trends.py
init_admin.py
services/
auth_service.py
fcm_service.py
notification_service.py
client_service.py
service_service.py
invoice_service.py
notification_orchestrator.py
... (others)
templates/
base_auth.html
home.html
authentication/
login.html (also in apps authentication templates)
register_client.html
register_provider.html
forgot_password.html
verify_otp.html
reset_password.html
pending_approval.html
subscription/
upgrade.html
(other subscription templates)
dashboard/
various admin templates referenced above
service/
create.html
edit.html
(other site templates)
static/
css/
js/
images/
venv/ (legacy virtualenv; may be present; large)
...
manage.py (entry point)
Other notable files at repo root or within app folders:

requirements.txt
firebase service account JSON (handybase-74eb1-...)
many compiled .pyc files scattered in pycache folders across the repo
.venv/ contains uvicorn, fastapi, and other package binaries
front-end Django manage entry is at manage.py (the one you run with FASTAPI_BASE_URL=... previously)




PS C:\Users\hp\OneDrive\Desktop> cd C:\redis
PS C:\redis> .\redis-server.exe



ADMIN - python3 -m app.scripts.init_admin create admin@handybase.com mypassword123 "System Admin" 