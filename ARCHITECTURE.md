# Medi Manage API — Architecture

This document describes the runtime architecture of the pharmacy management API. The diagrams use Mermaid and render directly on GitHub.

## System architecture

```mermaid
flowchart LR
    Customer[Customer] --> UserApp[MediUserApp<br/>Android]
    Shop[Shop admin] --> AdminApp[MediAdminApp<br/>Android]
    UserApp -->|HTTPS / JSON| API
    AdminApp -->|HTTPS / JSON| API

    subgraph API[Flask API]
        direction TB
        Server[Render or other host<br/>Gunicorn / WSGI]
        Factory[Application factory<br/>configuration and extensions]
        Routes[Versioned routes / blueprints<br/>JWT, role and request validation]
        Schemas[Request schemas]
        Services[Services<br/>accounts · products · inventory<br/>orders · reports · audit]
        Utils[Shared utilities<br/>responses · errors · idempotency · rate limits]
        Server --> Factory --> Routes
        Routes --> Schemas
        Routes --> Services
        Routes --> Utils
    end

    subgraph Storage[Data persistence]
        DBLayer[Database connection layer]
        LocalDB[(SQLite<br/>development and tests)]
        Turso[(Turso / hosted SQLite<br/>production when configured)]
        DBLayer --> LocalDB
        DBLayer --> Turso
    end

    subgraph External[External integrations]
        Redis[(Redis<br/>OTP · rate limits · token blocklist)]
        Memory[(In-memory store<br/>development fallback)]
        Cloudinary[Cloudinary<br/>images · prescriptions]
        Email[Email provider<br/>OTP · account messages]
    end

    Services --> DBLayer
    Services --> Redis
    Services -. development fallback .-> Memory
    Services --> Cloudinary
    Services --> Email
    Routes -->|JSON response| UserApp
    Routes -->|JSON response| AdminApp
```

## Request and order flow

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant UserApp as MediUserApp
    participant API as Flask API
    participant AdminApp as MediAdminApp
    actor Shop as Shop admin
    participant DB as SQLite / Turso

    Customer->>UserApp: Select medicines and place order
    UserApp->>API: Create order / checkout
    API->>DB: Save pending order
    API-->>UserApp: Order created
    opt Prescription required
        UserApp->>API: Upload prescription
        API-->>UserApp: Prescription attached
    end
    AdminApp->>API: Fetch pending order
    API-->>AdminApp: Order details and prescription
    Shop->>AdminApp: Review and approve
    AdminApp->>API: Approve order
    API->>DB: Update order status
    Shop->>AdminApp: Mark order as sold
    AdminApp->>API: Complete sale
    API->>DB: Apply FEFO stock deduction and create invoice
    API-->>UserApp: Order sold and invoice ready
    UserApp-->>Customer: Display invoice
```

## Deployment architecture

```mermaid
flowchart LR
    Source[Application source] --> Image[Docker image<br/>Python 3.12]
    Image --> Host[Production host<br/>for example Render]
    Host --> Start[Production start script]
    Start --> Migration[Run additive database migrations]
    Migration --> Gunicorn[Start Gunicorn WSGI workers]
    Gunicorn --> App[Flask application]
    App --> DB[(Turso hosted SQLite<br/>or configured SQLite file)]
    App --> Redis[(Redis, when configured)]
    App --> Media[Cloudinary, when configured]
    App --> Mail[Email provider, when configured]
```

## Component responsibilities

- **Routes and blueprints** handle HTTP concerns, authentication and authorization checks, request validation, and response formatting.
- **Schemas and utilities** provide shared input validation, standard JSON responses, error handling, idempotency, and rate limiting.
- **Services** implement pharmacy workflows, including FEFO inventory deductions and order processing.
- **Database layer** provides the configured SQLite/Turso access. Related stock and order updates are performed transactionally.
- **Integrations** provide OTP/token storage, media uploads, and transactional email, selected through environment configuration.
- **Production startup** runs database migrations before starting the Gunicorn WSGI server.

For setup, configuration, and testing details, see [README.md](README.md).
