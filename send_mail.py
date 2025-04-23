import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

load_dotenv()

async def send_email(to_email: str, subject: str, html_content: str):
    """
    Send email using SendGrid
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML content of the email
        
    Returns:
        dict: Response from SendGrid API
    """
    # Verify environment variables are loaded
    sendgrid_api_key ='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'
    from_email = os.getenv('SENDGRID_FROM_EMAIL') or os.getenv('SENDGRID_FROM_EMAIL')  # Handle typo
    
    if not sendgrid_api_key:
        return {"error": "SendGrid API key not configured"}
    if not from_email:
        return {"error": "From email not configured"}

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content)
    
    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        return {
            "status_code": response.status_code,
            "body": response.body,
            "headers": response.headers
        }
    except Exception as e:
        return {"error": f"SendGrid error: {str(e)}"}
