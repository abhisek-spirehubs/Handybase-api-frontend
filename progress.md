# HandyBase API - Technical Documentation

**Project:** HandyBase - Skilled Hands. Trusted Service.  
**Version:** 1.0.0  
**Date:** March 25, 2026  
**Backend Framework:** FastAPI (Python 3.10+)  
**Architecture:** RESTful API with WebSocket support  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Database Schema](#4-database-schema)
5. [API Endpoints](#5-api-endpoints)
6. [Services Layer](#6-services-layer)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Subscription & Feature Flags](#8-subscription--feature-flags)
9. [Background Tasks](#9-background-tasks)
10. [Real-time Features](#10-real-time-features)
11. [File Storage & Media](#11-file-storage--media)
12. [Notifications](#12-notifications)
13. [Rate Limiting](#14-rate-limiting)
14. [Error Handling](#15-error-handling)
15. [Deployment Configuration](#16-deployment-configuration)

---

## 1. Project Overview

HandyBase is a comprehensive service marketplace platform connecting clients with service providers. The backend provides:

- User management (Clients, Providers, Admins)
- Service listings with categories
- Booking system with calendar integration
- Real-time chat between clients and providers
- Payment and invoice management
- Subscription-based tier system
- Reviews and ratings
- Analytics and financial reporting
- Push notifications via Firebase Cloud Messaging

### Key Features

- **Multi-role system:** Client (Free/Paid), Provider (Tier 1/2/3), Admin
- **Subscription tiers:** Feature-based access control
- **Real-time chat:** WebSocket-based messaging with Redis Pub/Sub
- **File uploads:** Support for images, videos, documents
- **PDF generation:** Invoices and financial reports
- **Email notifications:** SMTP-based email system
- **Push notifications:** Firebase Cloud Messaging (FCM)

---

## 2. Technology Stack

### Core Framework
- **FastAPI** 0.129.0 - Modern async Python web framework
- **Uvicorn** 0.40.0 - ASGI server

### Database & ODM
- **MongoDB** - Primary database
- **Motor** 3.7.1 - Async MongoDB driver
- **Beanie** 2.0.1 - Async ODM (Object Document Mapper)

### Authentication & Security
- **Python-Jose** 3.5.0 - JWT token handling
- **Passlib** 1.7.4 - Password hashing (bcrypt)
- **bcrypt** 4.0.1 - Password hashing algorithm
- **Pydantic** 2.10.6 - Data validation and settings

### Email & Communication
- **aiosmtplib** 3.0.1 - Async SMTP client
- **Jinja2** 3.1.4 - Email template rendering

### Real-time & Caching
- **Redis** 4.6.0 - Pub/Sub for WebSocket, caching
- **aioredis** - Async Redis client

### File Handling & PDFs
- **ReportLab** 4.4.10 - PDF generation

### Firebase
- **firebase-admin** 7.2.0 - Push notifications

### Scheduling
- **APScheduler** 3.11.2 - Background job scheduler

### Utilities
- **python-dotenv** 1.2.1 - Environment variables
- **loguru** 0.7.3 - Structured logging
- **slowapi** 0.1.6 - Rate limiting
- **python-multipart** 0.0.22 - Form data handling

---

## 3. System Architecture

### Project Structure

```
handy-base-api/
├── app/
│   ├── main.py                    # FastAPI app initialization & lifespan
│   ├── api/
│   │   └── v1/
│   │       ├── router.py          # API route aggregator
│   │       ├── endpoints/         # Individual endpoint modules
│   │       └── sockets/           # WebSocket handlers
│   ├── core/
│   │   ├── config.py              # Configuration (pydantic-settings)
│   │   ├── database.py            # MongoDB connection
│   │   ├── exceptions.py          # Custom exceptions
│   │   ├── handlers.py            # Exception handlers
│   │   ├── firebase.py            # Firebase initialization
│   │   ├── redis_client.py        # Redis connection
│   │   └── socket_manager.py      # WebSocket connection manager
│   ├── dependencies/
│   │   ├── auth.py                # Authentication dependencies
│   │   ├── rate_limit.py          # Rate limiting decorators
│   │   └── subscription.py        # Subscription feature checks
│   ├── models/                    # Beanie document models
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── services/                  # Business logic layer
│   ├── middleware/
│   │   └── logging.py             # Request logging middleware
│   ├── templates/                 # Email templates
│   ├── utils/                     # Helper utilities
│   ├── scripts/                   # Utility scripts (init_admin, etc.)
│   └── background_task.py         # Background task definitions
├── media/                         # Uploaded files (avatars, documents, videos)
├── logs/                          # Application logs
├── requirements.txt
├── readme.md
└── .env                           # Environment configuration
```

### Request Flow

1. **Request** → FastAPI router
2. **Dependencies** → Auth, rate limiting, subscription checks
3. **Endpoint** → Validates input via Pydantic schemas
4. **Service Layer** → Business logic, database operations
5. **Models** → Beanie documents (MongoDB)
6. **Response** → Pydantic serialization → JSON

---

## 4. Database Schema

### Core Models

#### User Model (`models/user.py`)
```python
- id: ObjectId
- email: EmailStr (unique)
- password: Optional[str] (hashed)
- email_verified: bool = False
- user_type: UserRole (CLIENT, PROVIDER, ADMIN)
- status: UserStatus (ACTIVE, INACTIVE)
- fname: Optional[str]
- lname: Optional[str]
- full_name: Optional[str]
- phone: Optional[str]
- date_of_birth: Optional[datetime]
- avatar_url: Optional[str]
- last_login: Optional[datetime]

# OTP fields
- otp_code: Optional[str] (SHA-256 hash)
- otp_expire: Optional[int] (unix timestamp, 5 min validity)
- otp_verified: bool = False
- otp_verified_at: Optional[int] (unix timestamp, 10-min reset window)

# Session/Token
- token: Optional[str]

# Provider-specific fields
- business_name: Optional[str]
- description: Optional[str]
- experience_years: Optional[int]
- address: Optional[str]
- profile_image: Optional[str]
- portfolio_images: List[str]
- documents: List[str]
- rating: float = 0.0
- total_reviews: int = 0
- is_provider_approved: bool = False
- provider_rejection_reason: Optional[str]
- website_url: Optional[str]
- social_links: Optional[dict] (e.g., {"instagram": "url", "facebook": "url"})

# Subscription cache (mirrors Subscription document)
- subscription_plan: Optional[str] (e.g., "provider_tier1")
- subscription_expires_at: Optional[datetime] (None = free plan never expires)

# Portfolio videos (Tier 3)
- portfolio_videos: List[dict]

# Audit trail (from LogBase)
- created_at: datetime
- updated_at: datetime
- created_by: Optional[str]
- updated_by: Optional[str]
- is_deleted: bool = False
```

#### Provider Profile (`models/provider.py`)
```python
- id: ObjectId (references User)
- business_name: str
- bio: Optional[str]
- profile_image: Optional[str]
- portfolio_image: Optional[str]
- services: List[str] (service types offered)
- website_url: Optional[str]
- social_links: Optional[dict]
- is_approved: bool
- approval_date: Optional[datetime]
- rejection_reason: Optional[str]
- rating: float (average)
- review_count: int
```

#### Client Profile (`models/client.py`)
```python
- id: ObjectId (references User)
- status: Enum (ACTIVE, INACTIVE)
```

#### Category (`models/category.py`)
```python
- id: ObjectId
- name: str
- description: Optional[str]
- parent_id: Optional[ObjectId] (self-reference for subcategories)
- icon: Optional[str] (uploaded image URL)
- status: Enum (ACTIVE, INACTIVE)
- order: int
```

#### Service (`models/service.py`)
```python
- id: ObjectId
- provider_id: ObjectId (references User)
- category_id: ObjectId (references Category)
- title: str
- description: Optional[str]
- price: float
- duration: int (minutes)
- city: Optional[str]
- state: Optional[str]
- image: Optional[str]
- approval_status: Enum (PENDING, APPROVED, REJECTED)
- rejection_reason: Optional[str]
- is_active: bool
```

#### Booking (`models/booking.py`)
```python
- id: ObjectId
- booking_number: str (unique, human-readable)
- client_id: ObjectId
- provider_id: ObjectId
- service_id: ObjectId
- scheduled_date: datetime
- address: Optional[str]
- note: Optional[str]
- status: Enum (PENDING, CONFIRMED, COMPLETED, CANCELLED)
- cancellation_reason: Optional[str]
- payment_status: Enum (PENDING, PAID, REFUNDED)
- payment_id: Optional[str]
- amount: float
```

#### Chat Room (`models/chat_room.py`)
```python
- id: ObjectId
- booking_id: ObjectId (unique, 1-to-1 with booking)
- client_id: ObjectId
- provider_id: ObjectId
- last_message_at: Optional[datetime]
- unread_count_client: int
- unread_count_provider: int
```

#### Chat Message (`models/chat_message.py`)
```python
- id: ObjectId
- chat_room_id: ObjectId
- sender_id: ObjectId
- text: Optional[str]
- attachment_url: Optional[str]
- attachment_type: Optional[str]
- is_read: bool
- read_at: Optional[datetime]
```

#### Review (`models/review.py`)
```python
- id: ObjectId
- booking_id: ObjectId (unique)
- provider_id: ObjectId
- client_id: ObjectId
- rating: float (1-5)
- comment: Optional[str]
- media_urls: List[str]
- is_deleted: bool
```

#### Client Review (`models/client_review.py`) - Provider rates client
```python
- id: ObjectId
- booking_id: ObjectId (unique)
- provider_id: ObjectId
- client_id: ObjectId
- rating: float (1-5)
- comment: str (internal, not shown to client)
```

#### Plan (`models/plan.py`) - Two collections: client_plans, provider_plans
```python
- id: ObjectId
- name: str
- plan_type: Enum (client_free, client_paid, provider_tier1, tier2, tier3)
- price: float
- currency: str (default "USD")
- billing_cycle: Enum (MONTHLY, YEARLY)
- features: dict (JSON of feature flags)
- is_active: bool
```

#### Subscription (`models/subscription.py`) - Two collections: client_subscriptions, provider_subscriptions
```python
- id: ObjectId
- user_id: ObjectId
- plan_id: ObjectId
- status: Enum (ACTIVE, EXPIRED, CANCELLED)
- start_date: datetime
- expiry_date: datetime
- auto_renew: bool
- payment_id: Optional[str]
```

#### Invoice (`models/invoice.py`)
```python
- id: ObjectId
- invoice_number: str (unique)
- user_id: ObjectId
- subscription_id: Optional[ObjectId]
- amount: float
- currency: str
- status: Enum (PENDING, PAID, OVERDUE)
- due_date: datetime
- paid_date: Optional[datetime]
- pdf_url: Optional[str]
```

#### Notification (`models/notification.py`)
```python
- id: ObjectId
- user_id: ObjectId
- type: str (e.g., "booking_confirmed", "new_message")
- title: str
- body: str
- data: Optional[dict] (payload)
- is_read: bool
- created_at: datetime
```

#### FCM Token (`models/fcm_token.py`)
```python
- id: ObjectId
- user_id: ObjectId
- token: str (unique)
- device_id: Optional[str]
- platform: Optional[str] (ios, android, web)
- is_active: bool
- last_used_at: Optional[datetime]
```

#### Support Ticket (`models/support_ticket.py`)
```python
- id: ObjectId
- ticket_number: str (unique)
- user_id: ObjectId
- category: Enum (TECHNICAL, BILLING, ACCOUNT, OTHER)
- subject: str
- description: str
- status: Enum (OPEN, IN_PROGRESS, RESOLVED, CLOSED)
- admin_notes: Optional[str]
- resolved_at: Optional[datetime]
```

#### Announcement (`models/announcement.py`)
```python
- id: ObjectId
- title: str
- body: str
- is_active: bool
- target_roles: List[str] (e.g., ["client", "provider"])
- created_by: ObjectId (admin)
- broadcast_at: Optional[datetime]
```

#### Video Portfolio (`models/video_portfolio.py`)
```python
- id: ObjectId
- provider_id: ObjectId
- video_url: str
- title: Optional[str]
- description: Optional[str]
- order: int
```

#### Additional Models
- `JobRequest` - Multi-contractor job postings
- `JobApplication` - Provider applications to jobs
- `Quotation` - Price quotes from providers to clients
- `ProviderAvailability` - Weekly schedule and blocked dates
- `ProviderSubscription` / `ClientSubscription` - Subscription records
- `ProviderPlan` / `ClientPlan` - Plan definitions
- `Invoice` - Billing invoices
- `FinancialReport` - Generated financial summaries
- `Analytics` - Provider analytics data
- `DocumentExchange` - Shared documents in chats/bookings
- `SharedDocument` - Document metadata

---

## 5. API Endpoints

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication
All protected endpoints require:
```
Authorization: Bearer <jwt_token>
```

Token obtained from: `POST /auth/login`

---

### Technical Progress Summary

All endpoints listed below are fully implemented and functional (✅ Complete).

---

### Health Check

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/health` | GET | Health check endpoint | ✅ Complete |

---

### Authentication (`/auth`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/login` | POST | User login with email/password | ✅ Complete |
| `/logout` | POST | User logout (clear FCM token) | ✅ Complete |
| `/users` | POST | Create user (admin only) | ✅ Complete |
| `/me` | GET | Get current user profile | ✅ Complete |
| `/profile` | PUT | Update user profile | ✅ Complete |
| `/change-password` | PATCH | Change password (authenticated) | ✅ Complete |
| `/send-otp` | POST | Send OTP for verification | ✅ Complete |
| `/verify-otp` | POST | Verify OTP code | ✅ Complete |
| `/change-password-with-otp` | POST | Reset password via OTP | ✅ Complete |

---

### Clients (`/clients`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | POST | Register new client | ✅ Complete |
| `/profile` | GET | Get current client profile | ✅ Complete |
| `/update` | PUT | Update client profile | ✅ Complete |
| `/me/delete-account` | POST | Delete account with OTP verification | ✅ Complete |
| `/` | GET | List all users (admin only) | ✅ Complete |
| `/{user_id}` | GET | Get user by ID (admin) | ✅ Complete |
| `/{user_id}` | PATCH | Update user (admin) | ✅ Complete |
| `/{user_id}` | DELETE | Deactivate user (admin) | ✅ Complete |

---

### Providers (`/providers`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/register` | POST | Register as provider (pending approval) | ✅ Complete |
| `/` | GET | List approved providers (public) | ✅ Complete |
| `/admin` | GET | List all providers with filters (admin) | ✅ Complete |
| `/me` | GET | Get own provider profile | ✅ Complete |
| `/me` | PUT | Update own provider profile | ✅ Complete |
| `/{provider_id}` | GET | Get provider by ID | ✅ Complete |
| `/{provider_id}/approve` | PATCH | Approve provider (admin) | ✅ Complete |
| `/{provider_id}/reject` | PATCH | Reject provider (admin) | ✅ Complete |
| `/{provider_id}` | DELETE | Soft delete provider (admin) | ✅ Complete |

---

### Categories (`/categories`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | GET | List categories (public sees active only) | ✅ Complete |
| `/{category_id}` | GET | Get single category | ✅ Complete |
| `/{category_id}/subcategories` | GET | Get all subcategories | ✅ Complete |
| `/{category_id}/services` | GET | Get services in category | ✅ Complete |
| `/` | POST | Create category (admin) | ✅ Complete |
| `/{category_id}` | PUT | Update category (admin) | ✅ Complete |
| `/{category_id}/status` | PATCH | Toggle category status (admin) | ✅ Complete |

---

### Services (`/services`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | GET | List services with filters (role-aware) | ✅ Complete |
| `/{service_id}` | GET | Get single service | ✅ Complete |
| `/` | POST | Create service (provider) | ✅ Complete |
| `/{service_id}` | PUT | Update service (provider own) | ✅ Complete |
| `/{service_id}/approval` | PATCH | Approve/reject service (admin) | ✅ Complete |
| `/{service_id}` | DELETE | Soft delete service | ✅ Complete |

**GET /services Filters:**
- `page`, `limit` - Pagination
- `search` - Title search
- `category_id` - Filter by category
- `city`, `state` - Location filter
- `min_price`, `max_price` - Price range
- `sort_by` - newest/oldest/price_low/price_high
- `approval_status` - PENDING/APPROVED/REJECTED (admin/provider)
- `provider_id` - Filter by provider

---

### Availability (`/availability`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/me` | GET | Get my availability schedule (Tier 2+) | ✅ Complete |
| `/schedule` | PUT | Set weekly schedule (Tier 2+) | ✅ Complete |
| `/block` | POST | Block specific dates (Tier 2+) | ✅ Complete |
| `/unblock` | POST | Unblock dates (Tier 2+) | ✅ Complete |
| `/slots` | GET | Get available slots for booking | ✅ Complete |

---

### Bookings (`/bookings`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | POST | Create booking (client paid) | ✅ Complete |
| `/` | GET | List bookings (role-aware) | ✅ Complete |
| `/{booking_id}` | GET | Get single booking (participants only) | ✅ Complete |
| `/{booking_id}` | PUT | Update booking (while PENDING, client only) | ✅ Complete |
| `/{booking_id}/status` | PATCH | Update booking status (confirm/complete/cancel) | ✅ Complete |
| `/{booking_id}` | DELETE | Cancel booking (participants) | ✅ Complete |

**Booking Status Flow:**
- PENDING → CONFIRMED (provider)
- PENDING → CANCELLED (client/provider)
- CONFIRMED → COMPLETED (provider)
- CONFIRMED → CANCELLED (client/provider)

---

### Chat (`/chats`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/{booking_id}` | GET | Get chat room for confirmed booking | ✅ Complete |
| `/{booking_id}/messages` | POST | Send message in chat | ✅ Complete |
| `/{booking_id}/messages` | GET | Get paginated chat messages | ✅ Complete |
| `/{booking_id}/read` | PATCH | Mark messages as read | ✅ Complete |
| `/conversations/list` | GET | Get all conversations with unread counts | ✅ Complete |
| `/{booking_id}/unread-count` | GET | Get unread count for conversation | ✅ Complete |
| `/unread-count/total` | GET | Get total unread count across all chats | ✅ Complete |

---

### Reviews (`/reviews`) - Client → Provider

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/all` | GET | List all reviews with filters (admin) | ✅ Complete |
| `/{provider_id}` | GET | Get provider's reviews (public) | ✅ Complete |
| `/{booking_id}` | POST | Submit review with media (client paid) | ✅ Complete |
| `/{review_id}` | PUT | Update own review (client) | ✅ Complete |
| `/{review_id}` | DELETE | Delete own review (client) | ✅ Complete |
| `/admin/{review_id}` | DELETE | Delete any review (admin) | ✅ Complete |

---

### Client Reviews (`/client-reviews`) - Provider → Client (Tier 3)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | POST | Rate a client (provider Tier 3) | ✅ Complete |
| `/` | GET | Get my submitted client ratings (provider) | ✅ Complete |
| `/client/{client_id}` | GET | Get client's received ratings (admin/Tier 3/paid client) | ✅ Complete |
| `/{review_id}` | DELETE | Delete own rating (provider) | ✅ Complete |

---

### Notifications (`/notifications`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | GET | Get paginated notifications | ✅ Complete |
| `/unread-count` | GET | Get unread notification count | ✅ Complete |
| `/read-all` | PATCH | Mark all notifications as read | ✅ Complete |
| `/{notification_id}/read` | PATCH | Mark single notification as read | ✅ Complete |
| `/{notification_id}` | DELETE | Delete notification | ✅ Complete |
| `/` | DELETE | Clear all notifications | ✅ Complete |

---

### Plans (`/plans`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | GET | List plans (public: active only, admin: all) | ✅ Complete |
| `/{plan_id}` | GET | Get single plan | ✅ Complete |
| `/client` | POST | Create client plan (admin) | ✅ Complete |
| `/provider` | POST | Create provider plan (admin) | ✅ Complete |
| `/{plan_id}` | PUT | Update plan (admin) | ✅ Complete |
| `/{plan_id}` | DELETE | Soft delete plan (admin) | ✅ Complete |

---

### Subscriptions (`/subscriptions`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/current` | GET | Get current subscription + features | ✅ Complete |
| `/history` | GET | Get subscription history | ✅ Complete |
| `/subscribe` | POST | Subscribe to a plan | ✅ Complete |
| `/upgrade` | POST | Upgrade subscription | ✅ Complete |
| `/renew` | POST | Renew subscription | ✅ Complete |
| `/cancel` | POST | Cancel subscription | ✅ Complete |

---

### Invoices (`/invoices`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | GET | List invoices (user: own, admin: all) | ✅ Complete |
| `/{invoice_id}` | GET | Get single invoice | ✅ Complete |
| `/{invoice_id}/pdf` | GET | Download invoice PDF | ✅ Complete |

---

### Admin Dashboard (`/admin`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/dashboard` | GET | Platform stats overview | ✅ Complete |
| `/subscriptions/expire` | POST | Manually expire stale subscriptions | ✅ Complete |
| `/subscriptions/warn` | POST | Send expiry warnings manually | ✅ Complete |

---

### Analytics (`/analytics`) - Tier 3 Providers Only

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/dashboard` | GET | Full analytics dashboard | ✅ Complete |
| `/engagement` | GET | Profile engagement metrics | ✅ Complete |
| `/booking-trends` | GET | Daily booking trends | ✅ Complete |

---

### Financial Reports (`/financial-report`) - Tier 3 Providers Only

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/summary` | GET | Earnings summary for period | ✅ Complete |
| `/report/download` | GET | Download PDF financial report | ✅ Complete |

---

### Video Portfolio (`/portfolio-videos`) - Tier 3 Providers Only

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | POST | Upload portfolio video | ✅ Complete |
| `/{provider_id}` | GET | Get provider's videos | ✅ Complete |
| `/{video_id}` | DELETE | Delete portfolio video | ✅ Complete |

---

### Quotations & Price Comparison (`/client`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/compare-prices` | GET | Compare provider prices (client paid) | ✅ Complete |
| `/quotations` | POST | Request quotation from provider | ✅ Complete |
| `/quotations` | GET | List my quotation requests (client) | ✅ Complete |
| `/quotations/{quotation_id}` | GET | Get single quotation | ✅ Complete |
| `/quotations/{quotation_id}/cancel` | POST | Cancel quotation (client) | ✅ Complete |
| `/quotations/{quotation_id}/accept` | POST | Accept quotation (provider) | ✅ Complete |
| `/quotations/{quotation_id}/reject` | POST | Reject quotation (provider) | ✅ Complete |

---

### Job Requests (`/job`) - Multi-Contractor Jobs

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | POST | Post a job request (client) | ✅ Complete |
| `/my` | GET | List my job posts (client) | ✅ Complete |
| `/open` | GET | Browse open jobs (provider) | ✅ Complete |
| `/{job_id}` | GET | Get job details (location visible after acceptance) | ✅ Complete |
| `/{job_id}` | PUT | Update job (while OPEN, client only) | ✅ Complete |
| `/{job_id}/cancel` | POST | Cancel job (client) | ✅ Complete |
| `/{job_id}/applications` | GET | View applications (client) | ✅ Complete |
| `/{job_id}/select-applicants` | POST | Select provider → creates booking (client) | ✅ Complete |
| `/{job_id}/apply` | POST | Apply to job (provider) | ✅ Complete |
| `/applications/{app_id}` | DELETE | Withdraw application (provider) | ✅ Complete |

---

### Document Exchange

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/chats/{booking_id}/documents` | POST | Upload document to chat | ✅ Complete |
| `/chats/{booking_id}/documents` | GET | List chat documents | ✅ Complete |
| `/bookings/{booking_id}/documents` | POST | Upload document to booking | ✅ Complete |
| `/bookings/{booking_id}/documents` | GET | List booking documents | ✅ Complete |
| `/documents/{document_id}` | DELETE | Delete document (uploader only) | ✅ Complete |

---

### Support Tickets (`/support`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/tickets` | GET | List tickets (user: own, admin: all) | ✅ Complete |
| `/tickets` | POST | Submit support ticket | ✅ Complete |
| `/{ticket_id}` | GET | Get ticket details (owner/admin) | ✅ Complete |
| `/{ticket_id}/reply` | POST | Admin reply via email + push | ✅ Complete |
| `/{ticket_id}/close` | POST | Close ticket (admin) | ✅ Complete |
| `/{ticket_id}/reopen` | POST | Reopen closed ticket (admin) | ✅ Complete |
| `/{ticket_id}` | DELETE | Soft delete ticket (admin) | ✅ Complete |

---

### Announcements (`/announcements`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/` | GET | List announcements (user: active, admin: all) | ✅ Complete |
| `/` | POST | Create and broadcast announcement (admin) | ✅ Complete |
| `/{announcement_id}` | GET | Get single announcement | ✅ Complete |
| `/{announcement_id}` | PUT | Update announcement (admin) | ✅ Complete |
| `/{announcement_id}` | DELETE | Delete announcement (admin) | ✅ Complete |

---

### Firebase Cloud Messaging (`/fcm`)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/token/register` | POST | Register device token | ✅ Complete |
| `/token/{token}` | DELETE | Unregister specific token | ✅ Complete |
| `/tokens` | DELETE | Unregister all tokens | ✅ Complete |

---

### WebSocket

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/ws` | WS | Real-time chat & notifications | ✅ Complete |

**Events:**
- `chat_message` - Send/receive real-time messages
- `notification` - Real-time notifications
- `typing` - Typing indicators

---

### Availability (`/availability`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/me` | Get my availability schedule | Provider (Tier 2+) |
| PUT | `/schedule` | Set weekly schedule | Provider (Tier 2+) |
| POST | `/block` | Block specific dates | Provider (Tier 2+) |
| POST | `/unblock` | Unblock dates | Provider (Tier 2+) |
| GET | `/slots` | Get available slots for booking | Public |

---

### Bookings (`/bookings`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/` | Create booking (client) | Client (Paid) |
| GET | `/` | List bookings (role-aware) | Authenticated |
| GET | `/{booking_id}` | Get single booking | Participant only |
| PUT | `/{booking_id}` | Update booking (while PENDING) | Client (own) |
| PATCH | `/{booking_id}/status` | Update status (confirm/complete/cancel) | Provider/Client |
| DELETE | `/{booking_id}` | Cancel booking | Participant |

**Booking Status Flow:**
```
PENDING → CONFIRMED (provider)
PENDING → CANCELLED (client/provider)
CONFIRMED → COMPLETED (provider)
CONFIRMED → CANCELLED (client/provider)
```

---

### Chat (`/chats`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/{booking_id}` | Get chat room for booking | Participant only |
| POST | `/{booking_id}/messages` | Send message | Participant only |
| GET | `/{booking_id}/messages` | Get paginated messages | Participant only |
| PATCH | `/{booking_id}/read` | Mark messages as read | Participant only |
| GET | `/conversations/list` | Get all conversations | Authenticated |
| GET | `/{booking_id}/unread-count` | Get unread count | Participant only |
| GET | `/unread-count/total` | Get total unread count | Authenticated |

**Note:** Chat rooms are auto-created when provider confirms booking.

---

### Reviews (`/reviews`)

Client → Provider reviews

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/all` | List all reviews (with filters) | Admin only |
| GET | `/{provider_id}` | Get provider's reviews | Public |
| POST | `/{booking_id}` | Submit review (with media) | Client (Paid) |
| PUT | `/{review_id}` | Update own review | Client (own) |
| DELETE | `/{review_id}` | Delete own review | Client (own) |
| DELETE | `/admin/{review_id}` | Delete any review | Admin only |

---

### Client Reviews (`/client-reviews`)

Provider → Client ratings (Tier 3 only)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/` | Rate a client | Provider (Tier 3) |
| GET | `/` | Get my submitted client ratings | Provider |
| GET | `/client/{client_id}` | Get client's received ratings | Admin/Client (Paid)/Provider (Tier 3) |
| DELETE | `/{review_id}` | Delete own rating | Provider (own) |

---

### Notifications (`/notifications`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/` | Get paginated notifications | Authenticated |
| GET | `/unread-count` | Get unread count | Authenticated |
| PATCH | `/read-all` | Mark all as read | Authenticated |
| PATCH | `/{notification_id}/read` | Mark single as read | Authenticated |
| DELETE | `/{notification_id}` | Delete notification | Authenticated |
| DELETE | `/` | Clear all notifications | Authenticated |

---

### Plans (`/plans`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/` | List plans (public sees active, admin sees all) | Public/Admin |
| GET | `/{plan_id}` | Get single plan | Public |
| POST | `/client` | Create client plan | Admin only |
| POST | `/provider` | Create provider plan | Admin only |
| PUT | `/{plan_id}` | Update plan | Admin only |
| DELETE | `/{plan_id}` | Soft delete plan | Admin only |

---

### Subscriptions (`/subscriptions`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/current` | Get current subscription + features | Authenticated |
| GET | `/history` | Get subscription history | Authenticated |
| POST | `/subscribe` | Subscribe to a plan | Authenticated |
| POST | `/upgrade` | Upgrade subscription | Authenticated |
| POST | `/renew` | Renew subscription | Authenticated |
| POST | `/cancel` | Cancel subscription | Authenticated |

---

### Invoices (`/invoices`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/` | List invoices (user: own, admin: all) | Authenticated |
| GET | `/{invoice_id}` | Get single invoice | Owner/Admin |
| GET | `/{invoice_id}/pdf` | Download PDF | Owner/Admin |

---

### Admin Dashboard (`/admin`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/dashboard` | Platform stats overview | Admin only |
| POST | `/subscriptions/expire` | Manually expire stale subscriptions | Admin only |
| POST | `/subscriptions/warn` | Manually send expiry warnings | Admin only |

---

### Analytics (`/analytics`) - Tier 3 Providers Only

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/dashboard` | Full analytics dashboard | Provider (Tier 3) |
| GET | `/engagement` | Profile engagement metrics | Provider (Tier 3) |
| GET | `/booking-trends` | Daily booking trends | Provider (Tier 3) |

**Dashboard includes:**
- Job performance (totals, completion rate, avg rating, revenue)
- Profile & service engagement (visits, views)
- Daily booking trend data

---

### Financial Reports (`/financial-report`) - Tier 3 Providers Only

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/summary` | Earnings summary for period | Provider (Tier 3) |
| GET | `/report/download` | Download PDF report | Provider (Tier 3) |

**Periods:** week, month, quarter, custom (with date range)

---

### Video Portfolio (`/portfolio-videos`) - Tier 3 Providers Only

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/` | Upload portfolio video | Provider (Tier 3) |
| GET | `/{provider_id}` | Get provider's videos | Public (limited) / Provider (own) |
| DELETE | `/{video_id}` | Delete video | Provider (own) |

**Limits:** Max 10 videos, max 100MB each

---

### Quotations & Price Comparison (`/client`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/compare-prices` | Compare provider prices | Client (Paid) |
| POST | `/quotations` | Request quotation from provider | Client (Paid) |
| GET | `/quotations` | List my quotation requests | Client |
| GET | `/quotations/{quotation_id}` | Get single quotation | Client/Provider (involved) |
| POST | `/quotations/{quotation_id}/cancel` | Cancel quotation | Client (own) |
| POST | `/quotations/{quotation_id}/accept` | Accept quotation (provider) | Provider |
| POST | `/quotations/{quotation_id}/reject` | Reject quotation (provider) | Provider |

---

### Job Requests (`/job`) - Multi-Contractor Jobs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/` | Post a job request | Client |
| GET | `/my` | List my job posts | Client |
| GET | `/open` | Browse open jobs (with location pin) | Provider |
| GET | `/{job_id}` | Get job details (location visible only after acceptance) | Participant/Admin |
| PUT | `/{job_id}` | Update job (while OPEN) | Client (own) |
| POST | `/{job_id}/cancel` | Cancel job | Client (own) |
| GET | `/{job_id}/applications` | View applications | Client (own) |
| POST | `/{job_id}/select-applicants` | Select provider → creates booking | Client (own) |
| POST | `/{job_id}/apply` | Apply to job | Provider |
| DELETE | `/applications/{app_id}` | Withdraw application | Provider (own) |

---

### Document Exchange

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/chats/{booking_id}/documents` | Upload doc to chat | Participant |
| GET | `/chats/{booking_id}/documents` | List chat documents | Participant |
| POST | `/bookings/{booking_id}/documents` | Upload doc to booking | Participant |
| GET | `/bookings/{booking_id}/documents` | List booking documents | Participant |
| DELETE | `/documents/{document_id}` | Delete document | Uploader only |

**Max file size:** 20MB  
**Allowed formats:** pdf, doc, docx, xls, xlsx, ppt, pptx, txt, csv, jpg, jpeg, png, zip

---

### Support Tickets (`/support`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/tickets` | List tickets (user: own, admin: all) | Authenticated |
| POST | `/tickets` | Submit support ticket | Authenticated |
| GET | `/{ticket_id}` | Get ticket details | Owner/Admin |
| POST | `/{ticket_id}/reply` | Admin reply (email + push) | Admin only |
| POST | `/{ticket_id}/close` | Close ticket | Admin only |
| POST | `/{ticket_id}/reopen` | Reopen closed ticket | Admin only |
| DELETE | `/{ticket_id}` | Soft delete ticket | Admin only |

---

### Announcements (`/announcements`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/` | List announcements (user: active only, admin: all) | Authenticated |
| POST | `/` | Create and broadcast announcement | Admin only |
| GET | `/{announcement_id}` | Get single announcement | Authenticated |
| PUT | `/{announcement_id}` | Update announcement | Admin only |
| DELETE | `/{announcement_id}` | Delete announcement | Admin only |

---

### Firebase Cloud Messaging (`/fcm`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/token/register` | Register device token | Authenticated |
| DELETE | `/token/{token}` | Unregister specific token | Authenticated |
| DELETE | `/tokens` | Unregister all tokens | Authenticated |

---

### WebSocket Endpoints

**Connection:** `ws://localhost:8000/api/v1/ws?token=<jwt_token>`

**Events:**
- `chat_message` - Receive/send real-time chat messages
- `notification` - Receive push notifications in real-time
- `typing` - Typing indicators

**Implementation:** See `app/api/v1/sockets/chat_socket.py`

---

## 6. Services Layer

All business logic is encapsulated in the `app/services/` directory.

### Core Services

#### `auth_service.py`
- `login()` - Authenticate user, return JWT
- `admin_create_user()` - Admin creates client/provider
- `get_me()` - Get current user profile
- `update_profile()` - Update common profile fields
- `change_password()` - Change password with old password
- `send_otp()` - Generate and send OTP to email
- `verify_otp()` - Verify OTP
- `change_password_with_otp()` - Reset password using OTP

#### `client_service.py` (UserService)
- `register_client()` - Client registration
- `get_client_by_id()` - Get client profile
- `get_me()` - Get own profile
- `update_client_profile()` - Update client profile
- `get_all_clients()` - List all clients (admin)
- `update_client_status()` - Activate/suspend client
- `delete_client()` - Soft delete client

#### `provider_service.py`
- `register_provider()` - Provider registration (pending approval)
- `get_providers()` - List approved providers (public)
- `get_providers_admin()` - List all providers (admin)
- `get_provider_by_id()` - Get provider profile
- `update_provider()` - Update own provider profile
- `approve_provider()` - Admin approves provider
- `reject_provider()` - Admin rejects provider
- `delete_provider()` - Soft delete provider

#### `category_service.py`
- `get_all()` - List categories (with status filtering)
- `get_by_id()` - Get single category
- `get_subcategories()` - Get child categories
- `get_services_by_category()` - Get services in category
- `create()` - Create category (admin)
- `update()` - Update category (admin)
- `toggle_status()` - Activate/deactivate category (admin)

#### `service_service.py`
- `get_services()` - List services with filters (role-aware)
- `get_by_id()` - Get single service
- `create_service()` - Create service (provider)
- `update_service()` - Update service (provider)
- `approve_service()` - Approve service (admin)
- `reject_service()` - Reject service (admin)
- `delete_service()` - Soft delete service

#### `availability_service.py`
- `get_availability()` - Get provider's full availability
- `set_weekly_schedule()` - Set recurring weekly schedule
- `block_dates()` - Block specific dates
- `unblock_dates()` - Unblock dates
- `get_available_slots()` - Calculate available slots for booking

#### `booking_service.py`
- `create_booking()` - Create new booking
- `get_client_bookings()` - Get client's bookings
- `get_provider_bookings()` - Get provider's bookings
- `get_all_bookings()` - Get all bookings (admin)
- `get_booking_by_id()` - Get single booking (access control)
- `update_booking()` - Update booking (client, while PENDING)
- `update_booking_status()` - Change booking status
- `cancel_booking()` - Cancel booking

#### `chat_service.py`
- `get_conversation()` - Get chat room with unread count
- `send_message()` - Send message (stores in Redis + MongoDB)
- `get_messages()` - Get paginated chat messages
- `mark_as_read()` - Mark messages as read
- `get_all_conversations()` - List all conversations with previews
- `get_total_unread_count()` - Total unread across all chats

#### `redis_chat_service.py`
- `sync_all_pending_rooms()` - Sync Redis chat data to MongoDB
- Background task for periodic sync (every 5 minutes)

#### `review_service.py`
- `get_provider_reviews()` - Get provider's reviews (public)
- `get_all_reviews()` - List all reviews (admin)
- `create_review()` - Submit review with media upload
- `update_review()` - Update own review
- `delete_review()` - Delete own review
- `admin_delete_review()` - Admin delete any review

#### `client_review.py`
- `create_client_review()` - Provider rates client
- `get_reviews_by_provider()` - Get provider's submitted client ratings
- `get_client_ratings()` - Get client's received ratings

#### `notification_service.py`
- `get_notifications()` - Get user's notifications
- `get_unread_count()` - Count unread notifications
- `mark_all_as_read()` - Mark all as read
- `mark_as_read()` - Mark single as read
- `delete_notification()` - Delete notification
- `clear_notifications()` - Clear all notifications

#### `plan_service.py`
- `get_client_plans()` - List client plans
- `get_provider_plans()` - List provider plans
- `get_plan_by_id()` - Get single plan
- `create_client_plan()` - Create client plan (admin)
- `create_provider_plan()` - Create provider plan (admin)
- `update_plan()` - Update plan (admin)
- `delete_plan()` - Soft delete plan (admin)

#### `subscription_service.py`
- `get_current_subscription_response()` - Get active subscription + features
- `get_subscription_history()` - Get all subscriptions (past + present)
- `subscribe()` - Create new subscription
- `upgrade_subscription()` - Upgrade to higher plan
- `renew_subscription()` - Renew current plan
- `cancel_subscription()` - Cancel subscription
- `expire_stale_subscriptions()` - Cron job: expire overdue subscriptions
- `warn_expiring_subscriptions()` - Cron job: send expiry warnings (7 days before)
- `get_user_features()` - Get feature flags for user based on subscription

#### `invoice_service.py`
- `get_user_invoices()` - Get user's invoices
- `get_invoice_by_id()` - Get single invoice (access control)
- `generate_pdf()` - Generate PDF invoice (ReportLab)

#### `availability_service.py` (already covered)

#### `analytics_service.py`
- `get_provider_dashboard()` - Full analytics dashboard
- `compute_engagement()` - Profile visit and service view counts
- `compute_booking_trends()` - Daily booking and revenue trends
- `record_profile_visit()` - Increment profile visit counter (background task)

#### `financial_report.py`
- `compute_financial_summary()` - Calculate earnings summary
- `generate_financial_report_pdf()` - Generate PDF financial report

#### `price_comparison_service.py`
- `compare_prices()` - Compare multiple providers for same service

#### `quotation_service.py`
- `create_quotation()` - Client requests quote from provider
- `get_client_quotations()` - Client's quotation requests
- `get_quotation_by_id()` - Get single quotation
- `accept_quotation()` - Provider accepts → creates booking
- `reject_quotation()` - Provider rejects quotation
- `cancel_quotation()` - Client cancels request

#### `job_request.py`
- `list_open_job_requests()` - Browse open jobs (providers)
- `list_client_job_requests()` - Client's job posts
- `create_job_request()` - Client posts job
- `get_job_by_id()` - Get job (with location visibility rules)
- `update_job_request()` - Update job (while OPEN)
- `cancel_job_request()` - Cancel job
- `apply_to_job()` - Provider applies
- `select_provider()` - Client selects provider → creates booking
- `withdraw_application()` - Provider withdraws application

#### `video_portfolio.py`
- `upload_video()` - Upload portfolio video (Tier 3)
- `list_videos()` - Get provider's videos
- `delete_video()` - Delete video

#### `push_service.py`
- `register_token()` - Register FCM token for user
- `deactivate_token()` - Unregister token
- `deactivate_all_tokens()` - Clear all tokens for user
- `send_notification()` - Send push notification to user(s)

#### `announcement_service.py`
- `get_all()` - List announcements
- `create_announcement()` - Create + broadcast to all users
- `get_by_id()` - Get single announcement
- `update()` - Update announcement
- `delete()` - Soft delete announcement

#### `support_ticket.py` (SupportService)
- `create_ticket()` - Submit support ticket
- `get_my_tickets()` - User's tickets
- `get_all_tickets()` - All tickets (admin)
- `get_ticket()` - Get single ticket (access control)
- `reply_ticket()` - Admin replies (email + push)
- `close_ticket()` - Close ticket (admin)
- `reopen_ticket()` - Reopen ticket (admin)
- `delete_ticket()` - Soft delete ticket (admin)

#### `admin_service.py`
- `get_dashboard_stats()` - Platform-wide statistics

---

## 7. Authentication & Authorization

### JWT Tokens

- **Algorithm:** HS256
- **Secret:** From `JWT_SECRET` env variable
- **Expiry:** 7 days (configurable via `JWT_EXPIRE_DAYS`)
- **Payload:** `{ "sub": user_id, "role": user_type, "exp": expiry }`

### Authentication Flow

1. Client sends credentials to `POST /auth/login`
2. Server validates credentials
3. Returns `{ "access_token": "...", "token_type": "bearer" }`
4. Client includes token in subsequent requests:
   ```
   Authorization: Bearer <token>
   ```

### Dependencies

#### `get_current_user`
- Extracts and validates JWT
- Returns `User` document
- Raises 401 if invalid/missing

#### `get_current_user_optional`
- Same as above but returns `None` instead of raising (for public endpoints that optionally know user)

#### `admin_required`
- Requires `user_type == ADMIN`
- Raises 403 if not admin

#### `client_or_admin_required`
- Allows client or admin

#### `require_feature(feature_name)`
- Checks user's subscription features
- Raises 403 if feature not enabled
- Used for tier-based access control

---

## 8. Subscription & Feature Flags

### Subscription Model

Two separate collections:
- `client_subscriptions` - for clients
- `provider_subscriptions` - for providers

Each references:
- `user_id` → User
- `plan_id` → ClientPlan or ProviderPlan

### Plan Collections

- `client_plans` - e.g., "Client Free", "Client Paid"
- `provider_plans` - e.g., "Provider Tier 1", "Tier 2", "Tier 3"

### Feature Flags (stored in Plan.features dict)

#### Client Features
```python
{
    "can_book": True,              # Can place bookings
    "can_leave_reviews": True,     # Can submit reviews
    "can_compare_prices": True,    # Can use price comparison
    "can_request_quotes": True,    # Can request quotations
}
```

#### Provider Features
```python
{
    "can_list_services": True,      # Can create services
    "can_use_calendar": True,      # Can manage availability
    "can_view_analytics": True,    # Can view analytics dashboard
    "can_rate_clients": True,      # Can rate clients
    "can_upload_videos": True,     # Can upload portfolio videos
}
```

### Feature Check

```python
from app.dependencies.subscription import require_feature

@router.post("/something")
async def some_endpoint(
    current_user: User = Depends(require_feature("can_book"))
):
    # Only users with can_book=True in their active plan can access
    pass
```

### Current Subscription Endpoint

`GET /subscriptions/current` returns:
```json
{
  "success": true,
  "data": {
    "plan": { ... },
    "start_date": "2026-01-01T00:00:00Z",
    "expiry_date": "2026-02-01T00:00:00Z",
    "status": "ACTIVE",
    "features": {
      "can_book": true,
      ...
    }
  }
}
```

---

## 9. Background Tasks

### APScheduler Jobs

Configured in `app/main.py` lifespan:

1. **expire_subscriptions** - Daily at 00:00
   - Calls `SubscriptionService.expire_stale_subscriptions()`
   - Marks subscriptions as EXPIRED if expiry_date < today

2. **warn_expiring_subscriptions** - Daily at 09:00
   - Calls `SubscriptionService.warn_expiring_subscriptions()`
   - Sends email warnings to users whose subscriptions expire in 7 days

### Periodic Redis Sync

- **Frequency:** Every 5 minutes
- **Task:** `periodic_redis_sync()` in `main.py`
- **Action:** `RedisChatService.sync_all_pending_rooms(ChatService)`
- **Purpose:** Sync unread message counts from Redis to MongoDB

### BackgroundTask Usage

FastAPI `BackgroundTasks` is used for:
- Sending emails asynchronously (registration, notifications, support replies)
- Push notification broadcasting
- Analytics tracking (profile visit recording)
- PDF generation (async)

---

## 10. Real-time Features

### WebSocket

**Connection URL:**
```
ws://localhost:8000/api/v1/ws?token=<jwt_token>
```

**Implementation:** `app/api/v1/sockets/chat_socket.py`

**Manager:** `app/core/socket_manager.py` - Redis Pub/Sub based

**Events:**
- `chat_message` - Send/receive real-time messages
- `notification` - Real-time notifications
- `typing` - Typing indicators

**Pub/Sub Channels:**
- `chat:{booking_id}` - Chat messages for a booking
- `notification:{user_id}` - User-specific notifications

### Redis Usage

- **Pub/Sub:** WebSocket message broadcasting
- **Chat unread counts:** Stored in Redis, synced to MongoDB periodically
- **Structure:** `unread:{user_id}:{booking_id}` → count

---

## 11. File Storage & Media

### Storage Location

- **Directory:** `media/` (mounted at `/media` via StaticFiles)
- **Subdirectories:**
  - `avatars/` - User profile pictures
  - `categories/` - Category icons
  - `providers/` - Provider profile/portfolio images
  - `reviews/` - Review media (images/videos)
  - `documents/` - Shared documents
  - `videos/` - Portfolio videos

### File Upload Handling

- **Validation:** File type, size limits
- **Naming:** UUID-based filenames to avoid collisions
- **Security:** Extension whitelisting, size limits
- **Storage:** Local filesystem (can be replaced with S3/Cloud Storage)

### Upload Endpoints

- `POST /services/{id}/image` - Service image
- `POST /clients/update` - Client avatar
- `POST /providers/register` - Provider profile/portfolio images
- `POST /reviews/{booking_id}` - Review media
- `POST /chats/{booking_id}/documents` - Chat documents
- `POST /bookings/{booking_id}/documents` - Booking documents
- `POST /portfolio-videos/` - Provider videos
- `POST /categories/` - Category icons

---

## 12. Notifications

### Types

1. **In-app notifications** - Stored in `notifications` collection
2. **Push notifications** - Sent via Firebase Cloud Messaging (FCM)
3. **Email notifications** - Sent via SMTP

### Notification Triggers

- Booking confirmed/cancelled/completed
- New chat message
- New review received
- Subscription expiry warning
- Support ticket reply
- Platform announcements (broadcast)
- Provider approval/rejection

### FCM Integration

- Device tokens stored in `fcm_tokens` collection
- Tokens registered via `POST /fcm/token/register`
- Push sent using `firebase-admin` SDK
- Multi-device support (multiple tokens per user)

### Email Templates

Located in `app/templates/`:
- `registration.html` - Welcome email
- `provider_approval.html` - Provider approval notification
- `provider_rejection.html` - Provider rejection notice
- `support_reply.html` - Support ticket response
- `subscription_expiry.html` - Expiry warning
- `announcement.html` - Broadcast announcement

---

## 13. Rate Limiting

### Implementation

- **Library:** `slowapi`
- **Storage:** In-memory (default) - can be configured for Redis
- **Decorator:** `@login_rate_limit()`, `@send_otp_rate_limit()`, etc.

### Current Limits

- **Login:** 5 attempts per 60 seconds
- **Send OTP:** 3 attempts per 60 seconds
- **Verify OTP:** 5 attempts per 60 seconds
- **Change Password (OTP):** 3 attempts per 60 seconds
- **Registration:** 3 attempts per hour per IP

### Customization

Rate limiters defined in `app/dependencies/rate_limit.py`:

```python
login_rate_limit = limiter.limit("5/minute")
send_otp_rate_limit = limiter.limit("3/hour")
# etc.
```

---

## 14. Error Handling

### Custom Exceptions

Located in `app/core/exceptions.py`:

- `AppException` - Base exception (status_code=500)
- `ValidationException` - 400 Bad Request
- `NotFoundException` - 404 Not Found
- `ForbiddenException` - 403 Forbidden
- `UnauthorizedException` - 401 Unauthorized
- `ConflictException` - 409 Conflict

### Exception Handlers

In `app/core/handlers.py`:

- `app_exception_handler` - Handles `AppException` and subclasses
- `validation_exception_handler` - Handles Pydantic validation errors (422)
- `generic_exception_handler` - Catches all other exceptions

### Error Response Format

```json
{
  "success": false,
  "error": "Human readable message",
  "code": "MACHINE_READABLE_CODE",
  "details": {}  // optional, for validation errors
}
```

---

## 15. Deployment Configuration

### Environment Variables

See `app/core/config.py` for all settings.

**Required:**
```
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=handybase_db
JWT_SECRET=your_jwt_secret_here
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=smtp_user
SMTP_PASSWORD=smtp_password
SMTP_FROM="noreply@example.com"
```

**Optional:**
```
ENV=local|staging|production
DEBUG=True|False
CORS_ORIGINS=["http://localhost:3000"]
API_V1_STR=/api/v1
JWT_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379
FIREBASE_CREDENTIALS_PATH=path/to/serviceAccountKey.json
```

### Running the Application

```bash
# Development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker (Optional)

Not included but can be added with:
- Python 3.11 slim base
- Install dependencies from requirements.txt
- Copy app code
- Expose port 8000
- Run uvicorn command

---

## 16. Additional Notes

### Database Indexes

Beanie models define indexes in `Settings.indexes`. Important indexes:

- `User.email` (unique)
- `Booking.booking_number` (unique)
- `ChatRoom.booking_id` (unique)
- `ChatMessage.chat_room_id` + `created_at` (for pagination)
- `Notification.user_id` + `is_read` + `created_at`
- `Review.provider_id` + `is_deleted`
- `Subscription.user_id` + `expiry_date` (for expiry cron)

### Soft Deletes

Most models support soft deletion via `is_deleted` flag. Deleted documents are filtered out in queries.

### Audit Trail

Models inheriting from `BaseLogWithStatus` include:
- `created_at`
- `updated_at`
- `created_by`
- `updated_by`

### Pagination

Standard pagination pattern:
```json
{
  "success": true,
  "total": 100,
  "page": 1,
  "limit": 10,
  "pages": 10,
  "has_next": true,
  "has_prev": false,
  "data": [...]
}
```

### Background Tasks Pattern

Services use FastAPI `BackgroundTasks` for async operations that should not block the response:
- Email sending
- Push notifications
- Analytics recording
- PDF generation

---

## Conclusion

This is a full-featured service marketplace backend with:
- ✅ Complete CRUD operations for all entities
- ✅ Role-based access control (Client, Provider, Admin)
- ✅ Subscription-based feature gating
- ✅ Real-time chat with WebSocket + Redis
- ✅ File uploads with validation
- ✅ PDF generation (invoices, reports)
- ✅ Push notifications (FCM)
- ✅ Email notifications (SMTP)
- ✅ Rate limiting
- ✅ Comprehensive error handling
- ✅ Background scheduled tasks
- ✅ Soft deletes and audit trails

The architecture follows clean separation of concerns with dedicated services, making it maintainable and testable.

---

**Document Version:** 1.0  
**Last Updated:** March 25, 2026  
**Maintained by:** HandyBase Development Team
