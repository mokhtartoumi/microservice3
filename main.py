from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from send_mail import send_email
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles  # Add this for static files

# Import the dashboard router
from dashboard import router as dashboard_router

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if you have any (for CSS/JS)

# Include the dashboard router
app.include_router(dashboard_router, prefix="/api")

class EmailRequest(BaseModel):
    to_email: str
    subject: str
    html_content: str

class ProblemNotification(BaseModel):
    to: str
    subject: str
    body: str

@app.post("/send-email/")
async def send_email_api(email_data: EmailRequest):
    response = await send_email(
        to_email=email_data.to_email,
        subject=email_data.subject,
        html_content=email_data.html_content
    )
    
    if "error" in response:
        error_detail = response["error"]
        if "Unauthorized" in error_detail or "401" in error_detail:
            error_detail += " (Check your SendGrid API key)"
        raise HTTPException(
            status_code=400 if "not configured" in error_detail else 500,
            detail=error_detail
        )
    
    return {"message": "Email sent successfully", "details": response}

@app.post("/notify/email")
async def notify_email(notification: ProblemNotification):
    # Create HTML content from the plain text body
    html_content = f"""
    <html>
        <body>
            <h2>{notification.subject}</h2>
            <p>{notification.body}</p>
            <p>Please check your dashboard for more details.</p>
            <footer>
                <p>This is an automated message - please do not reply directly.</p>
            </footer>
        </body>
    </html>
    """
    
    response = await send_email(
        to_email=notification.to,
        subject=notification.subject,
        html_content=html_content
    )
    
    if "error" in response:
        error_detail = response["error"]
        if "Unauthorized" in error_detail or "401" in error_detail:
            error_detail += " (Check your SendGrid API key)"
        raise HTTPException(
            status_code=400 if "not configured" in error_detail else 500,
            detail=error_detail
        )
    
    return {"message": "Notification email sent successfully", "details": response}

# Optional: Add a root endpoint that redirects to the dashboard
@app.get("/")
async def root():
    return {"message": "Welcome to the API. Visit /api/dashboard for the admin interface."}