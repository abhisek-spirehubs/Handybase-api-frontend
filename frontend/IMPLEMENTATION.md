# HandyBase Frontend — Implementation & Tech Stack

> **Purpose:** Reference document for interviews, code reviews, and onboarding.
> Describes every technology used, why it was chosen, and how each feature was built.

---

## 📌 Project Summary

HandyBase is a **service marketplace platform** connecting homeowners (clients) with verified professionals (providers). The frontend is a **server-rendered Django web application** that consumes a separate FastAPI REST + WebSocket backend. It supports three user roles — Client, Provider, and Admin — each with a dedicated dashboard experience.

---

## 🧰 Tech Stack

### Core Framework
| Tool | Version | Role |
|---|---|---|
| **Python** | 3.12 | Primary language for all backend-frontend logic |
| **Django** | Latest stable | Web framework — routing, sessions, templating, middleware |
| **Django Template Language (DTL)** | Built-in | Server-side HTML rendering with inheritance and includes |

### HTTP & API Communication
| Tool | Role |
|---|---|
| **httpx** | Synchronous HTTP client — used to call FastAPI endpoints from Django views |
| **Bearer Token Auth** | JWT from FastAPI injected into every `httpx` request via `Authorization` header |
| **Custom `APIClient` class** | Wraps `httpx.Client` in a context manager, handles errors, file uploads, and JSON parsing |

### Frontend Design & Styling
| Tool | Role |
|---|---|
| **Tailwind CSS (CDN)** | Utility-first CSS framework — no build step required |
| **CSS Custom Properties (Variables)** | Design token system — all colors, spacing, and radius defined in `:root` as HSL values |
| **Vanilla CSS (`app.css`)** | Auth page styles, form components, button variants, flash messages |
| **Glassmorphism** | `backdrop-blur-md` + semi-transparent `bg-background/80` on sticky header and sidebar |
| **Inline `@keyframes`** | Custom animations: `fade-in-up` (chat messages), `fadeUp` (hero text), `shAnim` (scroll indicator) |

### UI Component Libraries
| Tool | Role |
|---|---|
| **Preline UI** | Headless Tailwind component library — powers off-canvas mobile sidebar via `data-hs-overlay` attributes |

### Typography
| Font | Used On |
|---|---|
| **Sora** (Google Fonts) | Dashboard — modern geometric sans-serif |
| **Inter** (Google Fonts) | Home/landing page — clean marketing copy font |
| **DM Sans** (Google Fonts) | Auth pages (login, register) — friendly rounded font |

### Animation & Motion
| Tool | Role |
|---|---|
| **GSAP 3** (GreenSock) | Timeline-based JavaScript animation library |
| **ScrollTrigger plugin** | Pins hero section and maps scroll position to animation progress |
| **HTML5 Canvas API** | Used to render the 80-frame image sequence for the cinematic hero |

### Real-Time Communication
| Tool | Role |
|---|---|
| **Native Browser WebSocket API** | Real-time bidirectional chat — no external library (Socket.io not used) |
| **FastAPI WebSocket endpoint** | Backend socket handler at `/api/v1/ws/chat/{booking_id}?token=...` |

### Static File Serving
| Tool | Role |
|---|---|
| **WhiteNoise** | Django middleware that serves `/static/` files directly — no Nginx required |

### Session & State
| Tool | Role |
|---|---|
| **Django Signed Cookie Sessions** | `SESSION_ENGINE = "signed_cookies"` — stateless, no DB table for sessions |
| **`localStorage`** | Used in JavaScript to persist last-seen notification ID across page loads |

### Internationalization
| Tool | Role |
|---|---|
| **Django i18n** (`USE_I18N = True`) | Enables multi-language support throughout the app |
| **`LocaleMiddleware`** | Reads language preference from cookie and activates the correct translation |
| **`gettext` + `.po` files** | Translation strings stored in `frontend/locale/en/`, `es/`, `fr/` |
| **`{% trans %}` template tag** | Marks all user-facing strings for translation in HTML templates |

### Icons
| Tool | Role |
|---|---|
| **Inline SVG** | All icons are hand-crafted SVG elements — no icon font or sprite sheet |

---

## 🏗️ Architecture & Design Patterns

### 1. Server-Side Rendering (SSR) with Django
Every page is a **full HTML response** generated on the server. Django views fetch data from FastAPI, build a Python context dictionary, and pass it to a DTL template which produces the final HTML.

```
Browser Request → Django URL Router → View fetches data from FastAPI
→ Django Template renders HTML → Browser displays fully rendered page
```

### 2. Atomic Design Component System
Templates follow the **Atomic Design** methodology (Brad Frost):
- **Atoms** → `_button.html`, `_input.html`, `_badge.html` — smallest units
- **Molecules** → `_alerts.html`, `_language_switcher.html` — combinations of atoms
- **Organisms** → `_sidebar.html`, `_navbar.html`, `_footer.html` — complex UI sections

All organisms are pulled into pages via Django's `{% include %}` tag.

### 3. Template Inheritance
All dashboard pages use a single base layout:
```
_base_dashboard.html  ← Defines sidebar, header, notification JS, design tokens
    └── dashboard/provider/bookings.html  ← Only provides {% block content %}
    └── dashboard/client/bookings.html
    └── apps/chat/templates/chat/room.html
    ...
```

### 4. Role-Based Access Control (RBAC)
Three user roles — `client`, `provider`, `admin` — each enforced at the Django view level:
```python
if request.session.get("user", {}).get("user_type") != "provider":
    return redirect("auth:login")
```
Sidebar links, page content, and action buttons are conditionally rendered using `{% if request.session.user.user_type == 'provider' %}`.

### 5. Custom API Client (Bridge Pattern)
A single reusable `APIClient` class in `apps/core/api_client.py` acts as the bridge between Django and FastAPI:
```python
with get_api_client(request) as api:     # reads JWT from session
    resp = api.get("/bookings", params={"limit": 50})
    bookings = resp.get("data", [])
```
- Automatically attaches `Authorization: Bearer <token>` header
- Handles JSON decode errors, empty 204 responses, and 4xx/5xx errors
- Switches to a special `multipart/form-data` mode for file uploads

### 6. Design Token System (CSS Variables + Tailwind)
Colors are defined once as CSS HSL variables and then plugged into Tailwind's config:
```css
/* _base_dashboard.html <style> block */
:root {
    --primary: 25 35% 45%;         /* Earthy brown */
    --background: 0 0% 98%;
    --border: 214 32% 91%;
}
```
```javascript
// Tailwind config (inline script)
tailwind.config = {
    theme: { extend: { colors: {
        primary: 'hsl(var(--primary))',
        background: 'hsl(var(--background))',
    }}}
}
```
Result: You can use `bg-primary`, `text-foreground`, `border-border` as Tailwind classes anywhere.

---

## ✨ Feature Implementation Details

### 🎬 Cinematic Hero / Landing Page
**Tools:** GSAP 3, ScrollTrigger plugin, HTML5 Canvas API

**Implementation:**
1. 80 PNG frames are pre-loaded into an array using JavaScript `Image()` objects.
2. A `<canvas>` element fills the full hero viewport.
3. GSAP **pins** the hero section and maps `scrollY` to a frame counter (0–79) using `ScrollTrigger`.
4. On every scroll frame, `canvas.getContext("2d").drawImage()` renders the correct PNG — creating a smooth 3D animation synchronized to scroll.
5. Simultaneously, GSAP fades out hero text and fades in the CTA button at defined scroll depths.

---

### 🔐 Authentication Flow
**Tools:** Django Sessions, httpx, CSRF middleware

**Implementation:**
- Login form posts to Django → Django calls `POST /auth/login` via `httpx` → receives JWT access token.
- Token and user object stored in Django signed cookie session: `request.session["access_token"] = token`
- All subsequent page loads read the token from session and pass it to `APIClient`.
- Password reset uses a 3-step OTP flow: send email → verify OTP → set new password.

---

### 📊 Role-Based Dashboards
**Tools:** Django Template Language, session-based role detection

**Implementation:**
- After login, `user_type` (`client`/`provider`/`admin`) is stored in session.
- Django views check role and redirect unauthorized access.
- The sidebar (`_sidebar.html`) uses `{% if %}` blocks to conditionally show role-specific links.
- Active page is highlighted using `{% if request.path == url %}` comparisons.

---

### 🔔 Notification System (Polling + Toast)
**Tools:** Vanilla JavaScript `setInterval`, `fetch()`, Django context processor, `localStorage`

**Implementation:**
- A Django **context processor** (`notifications/context_processors.py`) runs on every page load, calls FastAPI `/notifications/unread-count`, and injects `unread_notifications_count` globally into all templates — powering the sidebar badge.
- In the base layout's `<script>`, `setInterval` runs every **10 seconds**, calling `fetch('/notifications/api/latest/')`.
- If a new notification ID is detected (compared to `localStorage`), a toast is dynamically built via `document.createElement` and injected into a fixed `#notification-toast-container` div.
- Toast animates in using CSS `transition` (translate + opacity) and auto-removes after 8 seconds.

---

### 💬 Real-Time Chat
**Tools:** Native WebSocket API, FastAPI WebSocket, CSS `@keyframes`

**Implementation:**
1. When a booking is confirmed, FastAPI automatically creates a **ChatRoom** document in MongoDB.
2. The chat room page passes `booking_id`, `user_id`, and `ws_token` (JWT) as Django template variables.
3. JavaScript opens: `new WebSocket("ws://localhost:8000/api/v1/ws/chat/{booking_id}?token={token}")`
4. On `socket.onmessage`:
   - `recent_messages` → sorts by `created_at`, renders all history at once.
   - `new_message` → appends single new message bubble with `insertAdjacentHTML`.
5. Message alignment: `sender_id === userId` → right (primary color), else → left (muted).
6. Other user's name shown above their messages using the `other_user_name` context variable from Django.
7. Auto-reconnect: `socket.onclose` triggers `setTimeout(connect, 3000)`.
8. Each message animates in via `@keyframes fade-in-up` CSS animation.

---

### 📅 Bookings (Create, View, Status Update)
**Tools:** Django Forms (POST), httpx API calls, Django Messages framework

**Implementation:**
- **Client** books a provider by selecting a service + date + address → Django posts to FastAPI `/bookings`.
- **Provider** confirms/completes/rejects via form POST buttons → Django calls `PATCH /bookings/{id}/status`.
- All booking lists are enriched server-side: service name, provider name, and client name are fetched from the User/Service collections and injected into the response before rendering.
- Cancellation requires a reason (enforced by FastAPI); provider rejection uses a hardcoded default reason.

---

### ⭐ Reviews
**Tools:** Star rating form, Django POST, httpx

**Implementation:**
- After a booking is `COMPLETED`, a "Rate" button appears linking to `{% url 'client_reviews:rate' booking_id=... %}`.
- Client submits a 1–5 star rating + comment → Django sends to FastAPI `/reviews`.
- FastAPI auto-recalculates provider's average rating using a MongoDB aggregation pipeline and updates the User document.

---

### 💳 Subscription Gating
**Tools:** FastAPI feature flags, Django redirect logic

**Implementation:**
- Each plan (`client_free`, `client_paid`, `provider_tier1/2/3`) has feature flags (e.g., `can_use_messaging`, `can_book`).
- FastAPI checks these flags before allowing actions like chat or booking.
- Django also reads `subscription_plan` from the session to show/hide UI elements (e.g., premium-only dashboard cards with `{% if is_premium %}`).

---

### 🌍 Multi-Language (i18n)
**Tools:** Django i18n, `LocaleMiddleware`, `gettext`, `.po` translation files

**Implementation:**
- All template strings wrapped with `{% trans "..." %}` or `{% blocktrans %}`.
- Language switcher form POSTs to Django's `set_language` view.
- Django saves language in a `django_language` cookie via `response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)`.
- `LocaleMiddleware` reads this cookie on every request and activates the correct translation catalog.
- Translations are stored in `frontend/locale/{lang}/LC_MESSAGES/django.po`.

---

### 👤 Profile Management
**Tools:** Django multipart form, httpx file upload

**Implementation:**
- Profile form submits name/phone/bio as form data + optionally an image file.
- For file uploads, `APIClient` drops the `Content-Type: application/json` header and creates a new `httpx` client that auto-generates `multipart/form-data` boundaries.
- After update, Django re-fetches the user data from FastAPI (`/auth/me` + `/providers/me`) and updates the session in-place — no re-login required.

---

## 📦 Python Dependencies

```
django      → Core web framework
httpx       → Synchronous HTTP client for FastAPI calls
whitenoise  → Static file serving middleware
```

## 🌐 JavaScript Libraries (CDN, no npm)

```
Tailwind CSS CDN     → Utility CSS, configured inline with design tokens
Preline UI           → Off-canvas sidebar and interactive UI components
GSAP 3               → Scroll-driven animations for the hero section
ScrollTrigger        → GSAP plugin for scroll-based animation control
```

---

## 🔁 Data Flow Summary

```
┌─────────────────────────┐
│  Browser (HTML + JS)    │
│  Tailwind CSS + GSAP    │
│  WebSocket (chat only)  │
└────────────┬────────────┘
             │ HTTP (httpx) — all non-chat requests
             ▼
┌─────────────────────────┐
│  Django Frontend Server │
│  Port: 8080             │
│  Views → Templates      │
│  Session Auth (cookies) │
└────────────┬────────────┘
             │ httpx HTTP calls with Bearer token
             ▼
┌─────────────────────────┐
│  FastAPI Backend        │
│  Port: 8000             │
│  REST + WebSocket       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  MongoDB + Redis        │
│  Data + Cache/Real-time │
└─────────────────────────┘
```

---

*Generated: 2026-05-05 | HandyBase Frontend v1.0*
