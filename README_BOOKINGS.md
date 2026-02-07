# Zoho Bookings Proxy API Documentation

This proxy handles appointment scheduling via Zoho Bookings. It simplifies the booking process by automatically searching for available slots if your preferred time is taken.

## 1. Setup
To use the Bookings API, ensure your Zoho account is connected via the dashboard and that you have added the `service_id` and `staff_id` (either in the database or via the API request).

## 2. API Endpoint

### Book Appointment
`POST x`

**Request Body (JSON):**
```json
{
    "tenant_id": "optional_unique_tenant_id",
    "service_id": "2681636000036207001",
    "staff_id": "2681636000010777001",
    "date": "2026-02-10",
    "time": "14:30",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+919876543210"
}
```

### Response Scenarios

#### Scenario A: Success (Booking Confirmed)
```json
{
    "status": "booking done",
    "booking_id": "#SC-00144",
    "details": {
        "booking_id": "#SC-00144",
        "service_name": "30 Mins Meeting",
        "staff_name": "Prem Anand",
        "start_time": "07-Feb-2026 14:00:00",
        "end_time": "07-Feb-2026 14:30:00",
        "customer_name": "Test User",
        "customer_email": "user@test.local",
        "time_zone": "Asia/Kolkata"
    }
}
```

#### Scenario B: Slot Taken (Auto-Discovery)
If the requested slot is busy, the proxy automatically finds available slots for that day or the following days (up to 7 days).
```json
{
    "status": "slot unavailable",
    "message": "The requested slot was taken. Here are available slots for 2026-02-07",
    "date": "2026-02-07",
    "available_slots": ["01:15 PM", "01:30 PM", "02:30 PM", "02:45 PM", "03:00 PM"]
}
```

## 3. Configuration in Project
The proxy will try to use the `tenant_id` to find the correct Zoho credentials. If `tenant_id` is missing, it falls back to the account marked as **Primary** in the dashboard.
